import inspect
import re

import importlib
import types
from lispy.context import ExecutionContext, MergedExecutionContext
from lispy.expression import ExpressionTree
from lispy.tokenizer import Token
from lispy.utils import load_stdlib


def unpack_bind(variable, value, bindings=None):
    """ binds value to variable, optionally unpacking
        (a, b) = (0, 2) results in a = 1 and b = 2
    """
    binds = bindings or {}
    if len(variable) != len(value):
        raise RuntimeError('cannot unpack "%s" to "%s": they have different length' % (
            value, variable
        ))

    for f, a in zip(variable, value):
        expand_f = isinstance(f, (list, tuple))
        expand_a = isinstance(a, (list, tuple))

        if expand_f and expand_a:
            unpack_bind(f, a, binds)
        elif expand_a or (not expand_a and not expand_f):
            binds[f] = a
        else:
            raise RuntimeError('cannot unpack "%s" to "%s"' % (
                a, ExpressionTree.to_string(f)
            ))

    return binds


class Function:
    def __init__(self, name, parameters, body, ctx):
        self.name = name
        self.parameters = parameters
        self.body = body
        self.ctx = ctx

        try:
            pos = self.parameters.index('&')
            if pos != len(self.parameters) - 2:
                raise SyntaxError('varargs must be in last position')
            self.has_varargs = True
        except ValueError:
            self.has_varargs = False

    def bind_parameters(self, args):
        bindings = {}

        n = len(self.parameters)
        if self.has_varargs:
            n -= 2

        for i in range(n):
            if isinstance(self.parameters[i], (tuple, list)):
                try:
                    unpack_bind(self.parameters[i], args[i], bindings)
                except TypeError as exc:
                    raise RuntimeError('cannot unpack parameters') from exc
            else:
                bindings[self.parameters[i]] = args[i]
        
        if self.has_varargs:
            bindings[self.parameters[-1]] = list(args[n:])

        return bindings

    def __call__(self, ctx, *args):
        bindings = self.bind_parameters(args)
        new_ctx = MergedExecutionContext(ExecutionContext(ctx, **bindings), self.ctx)
        yield CodeResult(self.body, new_ctx)

    def __eq__(self, other):
        if not isinstance(other, Function):
            return False
        return (self.name == other.name and
                self.parameters == other.parameters and
                self.body == other.body)

    def __str__(self):
        return '<function "%s">' % self.name

    def __repr__(self):
        return 'Function(%s, %s)' % (self.name, ', '.join(self.parameters))


class AnonymousFunction:
    def __init__(self, ctx, children):
        self.body = list(children)
        self.ctx = ctx

    def __call__(self, ctx, *args):
        bindings = {}
        for i, x in enumerate(args):
            bindings['%' + str(i)] = x

        new_ctx = MergedExecutionContext(ExecutionContext(bindings), ctx, self.ctx)
        yield CodeResult(self.body, new_ctx)

    def __eq__(self, other):
        return False

    def __str__(self):
        return '<anonymous function>'

    def __repr__(self):
        return 'AnonymousFunction'


class Macro(Function):
    def __init__(self, name, parameters, body, ctx):
        super(Macro, self).__init__(name, parameters, body, ctx)

    def __call__(self, ctx, *args):
        bindings = self.bind_parameters(args)

        new_ctx = MergedExecutionContext(ExecutionContext(bindings), ctx, self.ctx)
        code = yield CodeResult(self.body, new_ctx)
        yield CodeResult(code, ctx)

    def __eq__(self, other):
        if not isinstance(other, Macro):
            return False
        return (self.name == other.name and
                self.parameters == other.parameters and
                self.body == other.body)

    def __str__(self):
        return '<macro "%s">' % self.name

    def __repr__(self):
        return 'Macro(%s, %s)' % (self.name, ', '.join(self.parameters))


class EvaluationResult:
    """ Result of the evaluation of an expression """
    def __init__(self, expr, ctx, must_evaluate):
        self.expr = expr
        self.ctx = ctx
        self.must_evaluate = must_evaluate


class ValueResult(EvaluationResult):
    """ Result of the evaluation of an expression
        that does not have to be evaluated (i.e. it's a value)
    """
    def __init__(self, expr, ctx):
        super(ValueResult, self).__init__(expr, ctx, must_evaluate=False)


class CodeResult(EvaluationResult):
    """ Result of the evaluation of an expression
        that must be evaluated (i.e. it's some "code")
    """
    def __init__(self, expr, ctx):
        super(CodeResult, self).__init__(expr, ctx, must_evaluate=True)


class IterativeInterpreter:
    def __init__(self, ctx=None, with_stdlib=False):
        self.last_frame = None
        self.operation_stack = []
        self.result_stack = []

        self.ctx = ExecutionContext(ctx)
        if with_stdlib:
            load_stdlib(self)

    def print_stacktrace(self):
        print('Call Stack (most recent last):')
        for op in self.operation_stack[:-1]:
            if op.gi_code.co_name == '__call__':
                func = op.gi_frame.f_locals['self']

                print('  (%s %s)' % (getattr(func, 'name', '<anonymous>'), ' '.join([
                    '%s=%s' % (
                        formal, str(actual) if len(str(actual)) < 25 else str(actual)[:25] + ' ... '
                    ) for formal, actual in op.gi_frame.f_locals['bindings'].items()
                ])))
            elif op.gi_frame:
                print(' ', ExpressionTree.print_short_format(op.gi_frame.f_locals.get('expr', '<unknown>')))
            else:
                print('  <unavailable>')

        if self.last_frame and 'expr' in self.last_frame.f_locals:
            print('Exception happened here:', ExpressionTree.to_string(
                self.last_frame.f_locals['expr']
            ))

    def evaluate(self, expr, ctx=None):
        """
        Entry point for the evaluation of an expression.
        """
        ctx = ctx or self.ctx

        val = self.eval(expr.as_list(), ctx)
        if not inspect.isgenerator(val):
            return val

        self.operation_stack = [val]
        self.result_stack = [None]
        val = None

        while self.operation_stack:
            op = self.operation_stack[-1]

            if op is None:
                self.operation_stack.pop()
                continue

            # used for exception reporting
            # when an exception happens inside a generator its gi_frame is set to None
            # which is a pity, because it contains the exact spot that caused the exception
            self.last_frame = op.gi_frame

            val = self.result_stack[-1]
            try:
                res = op.send(val)
            except StopIteration:
                self.operation_stack.pop()
            else:
                self.result_stack.pop()
                if not isinstance(res, EvaluationResult):
                    val = self.eval(res, self.ctx)
                elif res.must_evaluate:
                    val = self.eval(res.expr, res.ctx)
                else:
                    val = res.expr

                if isinstance(val, types.GeneratorType):
                    self.operation_stack.append(val)
                    self.result_stack.append(None)  # to initialize the generator
                else:
                    self.result_stack.append(val)

        self.last_frame = None
        return val

    def eval(self, expr, ctx):
        if isinstance(expr, list):
            if not isinstance(expr[0], Token):
                return self.evaluate_function_call(expr, ctx)

            name = (expr[0].value
                    .replace('.', 'dot')
                    .replace('#', 'hash')
                    .replace("'", 'tick')
                    .replace('$', 'dollar'))
            args = expr[1:]

            try:
                handler = getattr(self, 'handle_' + name)
            except AttributeError:
                return self.evaluate_function_call(expr, ctx)
            else:
                try:
                    return handler(ctx, expr, *args)
                except TypeError as exc:
                    expected = inspect.getargspec(handler).args[3:]
                    raise SyntaxError('expected syntax: (%s %s)' % (
                        name, ' '.join('<%s>' % arg for arg in expected)
                    )) from exc
        elif isinstance(expr, Token):
            if expr.type == Token.TOKEN_IDENTIFIER:
                members = expr.value.split('.')

                obj = ctx[members[0]]
                for each in members[1:]:
                    obj = getattr(obj, each)
                return obj
            elif expr.type == Token.TOKEN_LITERAL:
                return expr.value
            elif expr.value == '~':
                raise RuntimeError('cannot un-quote outside a quote')
            elif expr.value[0] == "'":
                return Token(expr.value[1:])
            else:
                return ctx.get(expr.value, expr.value)
        else:
            return expr

    def ensure_identifier(self, token):
        if not isinstance(token, Token):
            raise SyntaxError('cannot use "%s" as an identifier' % token)

        if token.type != Token.TOKEN_IDENTIFIER:
            raise SyntaxError('"%s" is not a valid identifier' % token.value)
        else:
            return token.value

    def ensure_list_of_identifiers(self, lst):
        return [
            self.ensure_list_of_identifiers(x) if isinstance(x, (tuple, list))
            else self.ensure_identifier(x)
            for x in lst
        ]

    def evaluate_function_call(self, expr, ctx):
        fun = yield CodeResult(expr[0], ctx)
        args = []
        if not isinstance(fun, Macro):
            for child in expr[1:]:
                val = yield CodeResult(child, ctx) if child != '&' else child
                args.append(val)
        else:
            args = [e if not isinstance(e, Token) or e.value != '&' else '&' for e in expr[1:]]

        if len(args) > 1 and '&' in args:
            # unpack actual varargs
            if args[-2] == '&':
                args = args[:-2] + list(args[-1])
            else:
                raise SyntaxError('cannot have parameters after varargs')

        yield from self.call_function(fun, ctx, args)

    def call_function(self, fun, ctx, args):
        if isinstance(fun, (Function, AnonymousFunction, Macro)):
            yield CodeResult(fun(ctx, *args), ctx)
        elif hasattr(fun, '__call__'):
            val = fun(*args)
            yield ValueResult(val, ctx)
        else:
            raise RuntimeError('not a function: "%s"' % fun)

    def handle_macroexpand(self, ctx, expr, macro, *args):
        mac = yield CodeResult(macro, ctx)
        val = next(mac(ctx, *args))
        yield val

    def handle_if(self, ctx, expr, cond, iftrue, iffalse):
        cval = yield CodeResult(cond, ctx)
        if cval:
            yield CodeResult(iftrue, ctx)
        else:
            yield CodeResult(iffalse, ctx)

    def handle_let(self, ctx, expr, bindings, body):
        new_ctx = ExecutionContext(ctx)
        for i in range(0, len(bindings), 2):
            value = yield CodeResult(bindings[i + 1], new_ctx)
            if isinstance(bindings[i], (list, tuple)):
                names = self.ensure_list_of_identifiers(bindings[i])
                unpack_bind(names, value, new_ctx)
            else:
                name = self.ensure_identifier(bindings[i])
                new_ctx[name] = value

        yield CodeResult(body, new_ctx)

    def build_callable(self, callable_cls, ctx, expr, name, parameters, body):
        formal = []
        has_varargs = False
        for i, p in enumerate(parameters):
            if isinstance(p, Token):
                if p.value != '&':
                    formal.append(self.ensure_identifier(p))
                else:
                    formal.append('&')
                    has_varargs = True
            elif isinstance(p, list):
                if has_varargs:
                    raise SyntaxError('cannot use packed arguments after vararg')
                formal.append(self.ensure_list_of_identifiers(p))
            else:
                raise SyntaxError('cannot use as a parameter: %s' % p)

        f = callable_cls(self.ensure_identifier(name), formal, body, ctx)

        if ctx:  # put the callable in the same context, so as to allow recursive calls
            ctx[name.value] = f
        return ValueResult(f, ctx)

    def handle_defn(self, ctx, expr, name, parameters, body):
        yield self.build_callable(Function, ctx, expr, name, parameters, body)

    def handle_defmacro(self, ctx, expr, name, parameters, body):
        yield self.build_callable(Macro, ctx, expr, name, parameters, body)

    def handle_do(self, ctx, expr, *children):
        result = None
        it = IterativeInterpreter.vararg_iterator(children)
        for arg in it:
            if isinstance(arg, (Token, list)):
                val = yield CodeResult(arg, ctx)
                arg = it.send(val)
            result = yield ValueResult(arg, ctx)
        yield ValueResult(result, ctx)

    def handle_pyimport(self, ctx, expr, *modules):
        for mod in map(self.ensure_identifier, modules):
            ctx[mod] = importlib.import_module(mod)

    def handle_pyimport_from(self, ctx, expr, module, name):
        module = self.ensure_identifier(module)
        name = self.ensure_identifier(name)

        try:
            mod = importlib.import_module(module + '.' + name)
            ctx[name] = mod
        except ImportError:
            mod = importlib.import_module(module)
            ctx[name] = getattr(mod, name)

    def handle_dot(self, ctx, expr, member, obj):
        obj = yield CodeResult(obj, ctx)
        yield CodeResult(getattr(obj, self.ensure_identifier(member)), ctx)

    def handle_def(self, ctx, expr, *children):
        value = None
        for i in range(0, len(children), 2):
            name = self.ensure_identifier(children[i])
            value = yield CodeResult(children[i + 1], ctx)
            ctx[name] = value
        yield ValueResult(value, ctx)

    def handle_call(self, ctx, expr, fun, *args):
        return self.evaluate_function_call(expr, ctx)

    def handle_comment(self, ctx, expr, *children):
        pass

    def handle_in(self, ctx, expr, item, collection):
        it = yield CodeResult(item, ctx)
        coll = yield CodeResult(collection, ctx)
        yield ValueResult(it in coll, ctx)

    @staticmethod
    def vararg_iterator(vargs):
        iterating_on_vargs = False
        for arg in vargs:
            if isinstance(arg, Token) and arg.value == '&':
                iterating_on_vargs = True
                continue

            val = yield arg
            if iterating_on_vargs:
                yield from val
            else:
                yield val

    def handle_and(self, ctx, expr, *children):
        it = IterativeInterpreter.vararg_iterator(children)
        for arg in it:
            if isinstance(arg, (Token, list)):
                val = yield CodeResult(arg, ctx)
                arg = it.send(val)

            if not arg:
                yield ValueResult(False, ctx)
                break
        else:
            yield ValueResult(True, ctx)

    def handle_or(self, ctx, expr, *children):
        it = IterativeInterpreter.vararg_iterator(children)
        for arg in it:
            if isinstance(arg, (Token, list)):
                val = yield CodeResult(arg, ctx)
                arg = it.send(val)

            if arg:
                yield ValueResult(True, ctx)
                break
        else:
            yield ValueResult(False, ctx)

    def handle_hash(self, ctx, expr, *children):
        yield ValueResult(AnonymousFunction(ctx, children), ctx)

    def handle_tick(self, ctx, expr, *children):
        return self.handle_quote(ctx, expr, *children)

    def handle_quote(self, ctx, expr, *children):
        to_expand = [children]
        expanded = [[]]
        progress = [0]

        while True:  # bad design... but it's 2:41 AM
            if progress[-1] < len(to_expand[-1]):
                cur = to_expand[-1][progress[-1]]
                progress[-1] += 1

                if isinstance(cur, Token):
                    if cur.value == '~':
                        if progress[-1] == len(to_expand[-1]):
                            raise RuntimeError('nothing to un-quote')
                        val = yield CodeResult(to_expand[-1][progress[-1]], ctx)
                        progress[-1] += 1
                    else:
                        val = cur
                    expanded[-1].append(val)
                else:
                    to_expand.append(cur)
                    expanded.append([])
                    progress.append(0)
            else:
                to_expand.pop()
                progress.pop()
                res = expanded.pop()
                if not expanded:
                    yield ValueResult(res, ctx)
                    break

                expanded[-1].append(res)

    def handle_dollar(self, ctx, expr, val):
        name = val.value if isinstance(val, Token) else val
        yield ValueResult(ctx[name], ctx)

    def handle_match(self, ctx, expr, var, *cases):
        value = yield CodeResult(var, ctx)
        for pattern, result in cases:
            pattern_is_list = isinstance(pattern, (list, tuple))
            var_is_list = isinstance(value, (list, tuple))

            if pattern_is_list and var_is_list:
                names = self.ensure_list_of_identifiers(pattern)
                try:
                    binds = unpack_bind(names, value)
                except RuntimeError:
                    continue
                else:
                    yield CodeResult(result, ExecutionContext(ctx, **binds))
                    break
            elif not pattern_is_list:
                name = self.ensure_identifier(pattern)
                yield CodeResult(result, ExecutionContext(ctx, name=value))
                break
        else:
            raise RuntimeError('pattern matching failed')

    def handle_filter(self, ctx, expr, fn, coll):
        f = yield CodeResult(fn, ctx)
        c = yield CodeResult(coll, ctx)
        res = []
        for x in c:
            keep = yield self.call_function(f, ctx, [x])
            if keep:
                res.append(x)
        yield ValueResult(res, ctx)

    def handle_map(self, ctx, expr, fn, coll):
        f = yield CodeResult(fn, ctx)
        c = yield CodeResult(coll, ctx)
        res = []
        for x in c:
            fx = yield self.call_function(f, ctx, [x])
            res.append(fx)
        yield ValueResult(res, ctx)

