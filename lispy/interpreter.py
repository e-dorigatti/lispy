import inspect
import re

import importlib
import types
from lispy.context import ExecutionContext
from lispy.expression import ExpressionTree
from lispy.tokenizer import Token
from lispy.utils import load_stdlib


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

    def __call__(self, *args):
        if self.has_varargs:
            # pack arguments in varargs
            n = len(self.parameters) - 2
            bindings = dict(zip(self.parameters[:n], args[:n]))
            bindings[self.parameters[-1]] = list(args[n:])
        else:
            bindings = dict(zip(self.parameters, args))

        ctx = ExecutionContext(self.ctx, **bindings)
        yield CodeResult(self.body, ctx)

    def __eq__(self, other):
        if not isinstance(other, Function):
            return False
        return (self.name == other.name and
                self.parameters == other.parameters and
                self.body == other.body)

    def __str__(self):
        return '<function "%s">' % self.name


class AnonymousFunction:
    def __init__(self, ctx, children):
        self.body = list(children)
        self.ctx = ctx

    def __call__(self, *args):
        bindings = {}
        for i, x in enumerate(args):
            bindings['%' + str(i)] = x

        ctx = ExecutionContext(self.ctx, **bindings)
        yield CodeResult(self.body, ctx)

    def __eq__(self, other):
        return False

    def __str__(self):
        return '<anonymous function>'


class EvaluationResult:
    def __init__(self, expr, ctx, must_evaluate):
        self.expr = expr
        self.ctx = ctx
        self.must_evaluate = must_evaluate


class ValueResult(EvaluationResult):
    def __init__(self, expr, ctx):
        super(ValueResult, self).__init__(expr, ctx, must_evaluate=False)


class CodeResult(EvaluationResult):
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
        for op in self.operation_stack:
            if op.gi_code.co_name.startswith('handle_'):
                if op.gi_frame:
                    print(' ', ExpressionTree.print_short_format(op.gi_frame.f_locals['expr']))
                else:
                    print('  <unavailable>')
            elif op.gi_code.co_name == '__call__':
                func = op.gi_frame.f_locals['self']

                print('  (%s %s)' % (getattr(func, 'name', '<anonymous>'), ' '.join([
                    '%s=%s' % (
                        formal, str(actual) if len(str(actual)) < 25 else str(actual)[:25] + ' ... '
                    ) for formal, actual in op.gi_frame.f_locals['bindings'].items()
                ])))

        if self.last_frame and 'expr' in self.last_frame.f_locals:
            print('Exception happened here:', ExpressionTree.to_string(
                self.last_frame.f_locals['expr']
            ))

    def evaluate(self, expr, ctx=None):
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
                if res.must_evaluate:
                    val = self.eval(res.expr, res.ctx)
                else:
                    val = res.expr

                if isinstance(val, types.GeneratorType):
                    self.operation_stack.append(val)
                    self.result_stack.append(None)
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
                    .replace("'", 'tick'))
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
            else:
                return ctx.get(expr.value, expr.value)
        else:
            return expr

    def ensure_identifier(self, token):
        if token.type != Token.TOKEN_IDENTIFIER:
            raise SyntaxError('"%s" is not a valid identifier' % token.value)
        else:
            return token.value

    def evaluate_function_call(self, expr, ctx):
        evaluated = []
        for child in expr:
            val = (yield CodeResult(child, ctx)) if child != '&' else child
            evaluated.append(val)

        fun, args = evaluated[0], evaluated[1:]
        if len(args) > 1 and '&' in args:
            # unpack actual varargs
            if args[-2] == '&':
                args = args[:-2] + list(args[-1])
            else:
                raise SyntaxError('cannot have parameters after varargs')

        if hasattr(fun, '__call__'):
            val = fun(*args)
            yield val if isinstance(val, EvaluationResult) else ValueResult(val, ctx)
        else:
            raise NameError(fun)

    def handle_if(self, ctx, expr, cond, iftrue, iffalse):
        cval = yield CodeResult(cond, ctx)
        if cval:
            yield CodeResult(iftrue, ctx)
        else:
            yield CodeResult(iffalse, ctx)

    def handle_let(self, ctx, expr, bindings, body):
        new_ctx = ExecutionContext(ctx)
        for i in range(0, len(bindings), 2):
            name = self.ensure_identifier(bindings[i])
            value = yield CodeResult(bindings[i + 1], new_ctx)
            new_ctx[name] = value

        yield CodeResult(body, new_ctx)

    def handle_defn(self, ctx, expr, name, parameters, body):
        formal = [self.ensure_identifier(t) if t.value != '&' else '&'
                  for t in parameters]
        f = Function(self.ensure_identifier(name), formal, body, ctx)

        if ctx:
            ctx[name.value] = f
        yield ValueResult(f, ctx)

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
        except ModuleNotFoundError:
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