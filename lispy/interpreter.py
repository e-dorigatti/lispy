import importlib
import re
import inspect
import types

from lispy.excs import SyntaxErrorException, NameNotFoundException
from lispy.context import ExecutionContext
from lispy.expression import ExpressionTree
from lispy.context import ExecutionContext
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
                raise SyntaxErrorException('varargs must be in last position')
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

        c = ExecutionContext(self.ctx, **bindings)
        return self.evaluate(c)

    def __eq__(self, other):
        if not isinstance(other, Function):
            return False
        return (self.name == other.name and
                self.parameters == other.parameters and
                self.body == other.body)

    def __str__(self):
        return '<function "%s">' % self.name

    def evaluate(self, context):
        raise NotImplementedError


class BaseInterpreter:
    def evaluate(self, expr, ctx):
        raise NotImplementedError


class RecursiveInterpreter(BaseInterpreter):
    def evaluate(self, expr, ctx):
        name, args = expr.children[0], expr.children[1:]
        try:
            name = name.replace('.', 'dot')
            handler = getattr(self, 'handle_' + name)
        except AttributeError:
            return self.evaluate_function_call(expr, ctx)
        else:
            try:
                return handler(expr, ctx, *args)
            except TypeError:
                expected = inspect.getargspec(handler).args[3:]
                raise SyntaxErrorException('expected syntax: (%s %s)' % (
                    name, ' '.join('<%s>' % arg for arg in expected)
                ))

    def handle_dot(self, expr, ctx, member, obj):
        return getattr(obj, member)

    def handle_pyimport(self, expr, ctx, *modules):
        # (pyimport mod-1 ... mod-n)
        #
        # imports the given python module
        for mod in modules:
            ctx[mod] = importlib.import_module(mod)

    def handle_do(self, expr, ctx, *children):
        # (do e1 ... en)
        #
        # evaluates all expressions in order, and returns the
        # value of the last one. if an expression has side effects,
        # they will be visible afterwards (e.g. functions defined
        # in a do will be visible outside it)
        result = None
        for child in children:
            result = self.evaluate(child, ctx)
        return result

    def handle_let(self, expr, ctx, bindings, body):
        # (let (name-1 value-1 ... name-n value-n) <expression>)
        #
        # introduces new definitions in the context and evaluates
        # the expression. the definitions are discarded afterwards
        new_ctx = ExecutionContext(ctx)
        for name, value_expr in zip(bindings.children[:-1], bindings.children[1:]):
            value = self.eval(value_expr, new_ctx)
            new_ctx[name] = value
        return self.eval(body, new_ctx)

    def handle_defn(self, expr, ctx, name, parameters, body):
        # (defn <name> (arg-1 ... arg-n [& vararg]) <body>)
        #
        # introduces a new function. the last argument can be a vararg.

        class RecFunction(Function):
            def evaluate(fself, context):
                return self.evaluate(fself.body, context)

        f = RecFunction(name, parameters, body, ctx)
        if ctx:
            ctx[name] = f
        return f

    def handle_if(self, expr, ctx, cond, iftrue, iffalse):
        # (if <condition> <iftrue> <iffalse>)
        #
        # if condition evaluates to true then iftrue is evaluated and returned,
        # otherwise iffalse is evaluated and returned.
        if self.eval(cond, ctx):
            return self.eval(iftrue, ctx)
        else:
            return self.eval(iffalse, ctx)

    def evaluate_function_call(self, expr, ctx):
        # (<function> arg-1 ... arg-n [& vararg])
        #
        # evaluates to the value returned by the function called with the
        # given parameters. the last argument can be a vararg
        evaluated = [self.eval(child, ctx) for child in expr.children]
        fun, args = evaluated[0], evaluated[1:]

        if len(args) > 1 and '&' in args:
            # unpack actual varargs
            if args[-2] == '&':
                args = args[:-2] + list(args[-1])
            else:
                raise SyntaxErrorException('cannot have parameters after varargs')

        try:
            return fun(*args)
        except:
            print('Error while calling %s with args %s' % (fun, args))
            raise

    def eval(self, thing, ctx):
        if isinstance(thing, ExpressionTree):
            return self.evaluate(thing, ctx)
        else:
            if thing in ctx:
                return ctx[thing]
            elif isinstance(thing, (str, bytes)) and '.' in thing:
                members = thing.split('.')
                obj = ctx[members[0]]
                for each in members[1:]:
                    obj = getattr(obj, each)
                return obj
            else:
                return thing


class IterativeInterpreter(BaseInterpreter):
    def __init__(self, ctx=None, with_stdlib=False):
        self.expression_stack = []
        self.operation_stack = []
        self.result_stack = []

        self.ctx = ExecutionContext(ctx)
        if with_stdlib:
            load_stdlib(self)

    def evaluate(self, expr, ctx=None):
        ctx = ctx or self.ctx

        val = self.eval(expr, ctx)
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

            val = self.result_stack[-1]
            try:
                expr, ctx = op.send(val)
            except StopIteration:
                self.operation_stack.pop()
            else:
                self.result_stack.pop()
                res = self.eval(expr, ctx)
                if isinstance(res, types.GeneratorType):
                    self.operation_stack.append(res)
                    self.result_stack.append(None)
                else:
                    self.result_stack.append(res)

        return val

    def eval(self, expr, ctx):
        if isinstance(expr, ExpressionTree):
            if not isinstance(expr.children[0], Token):
                return self.evaluate_function_call(expr, ctx)

            name = expr.children[0].value.replace('.', 'dot')
            args = expr.children[1:]

            try:
                handler = getattr(self, 'handle_' + name)
            except AttributeError:
                return self.evaluate_function_call(expr, ctx)
            else:
                try:
                    return handler(ctx, expr, *args)
                except TypeError:
                    expected = inspect.getargspec(handler).args[3:]
                    raise SyntaxErrorException('expected syntax: (%s %s)' % (
                        name, ' '.join('<%s>' % arg for arg in expected)
                    ))
        elif isinstance(expr, Token):
            if expr.type == Token.TOKEN_IDENTIFIER:
                members = expr.value.split('.')

                obj = ctx[members[0]]
                for each in members[1:]:
                    obj = getattr(obj, each)
                return obj
            elif expr.type == Token.TOKEN_LITERAL:
                return expr.value
            else:  # if expr.type == Token.TOKEN_OTHER
                return ctx.get(expr.value, expr.value)
        else:
            return expr

    def ensure_identifier(self, token):
        if token.type != Token.TOKEN_IDENTIFIER:
            raise SyntaxErrorException('"%s" is not a valid identifier'
                                       '' % token.value)
        else:
            return token.value

    def evaluate_function_call(self, expr, ctx):
        evaluated = []
        for child in expr.children:
            val = (yield child, ctx) if child != '&' else child
            evaluated.append(val)

        fun, args = evaluated[0], evaluated[1:]
        if len(args) > 1 and '&' in args:
            # unpack actual varargs
            if args[-2] == '&':
                args = args[:-2] + list(args[-1])
            else:
                raise SyntaxErrorException('cannot have parameters after varargs')

        if hasattr(fun, '__call__'):
            try:
                yield fun(*args), ctx
            except:
                print('Error while calling %s with args %s' % (fun, ', '.join(map(str, args))))
                raise
        else:
            raise NameNotFoundException(fun)

    def handle_if(self, ctx, expr, cond, iftrue, iffalse):
        cval = yield cond, ctx
        if cval:
            yield iftrue, ctx
        else:
            yield iffalse, ctx

    def handle_let(self, ctx, expr, bindings, body):
        new_ctx = ExecutionContext(ctx)
        for i in range(0, len(bindings.children), 2):
            name = self.ensure_identifier(bindings.children[i])
            value = yield bindings.children[i + 1], new_ctx
            new_ctx[name] = value

        yield body, new_ctx

    def handle_defn(self, ctx, expr, name, parameters, body):
        class IterFunction(Function):
            def evaluate(fself, context):
                yield fself.body, context

        formal = [self.ensure_identifier(t) if t.value != '&' else '&'
                  for t in parameters.children]
        f = IterFunction(self.ensure_identifier(name), formal, body, ctx)

        if ctx:
            ctx[name.value] = f
        yield f, ctx

    def handle_do(self, ctx, expr, *children):
        result = None
        for child in children:
            result = yield child, ctx
        yield result, ctx

    def handle_pyimport(self, ctx, expr, *modules):
        for mod in map(self.ensure_identifier, modules):
            ctx[mod] = importlib.import_module(mod)

    def handle_dot(self, ctx, expr, member, obj):
        obj = yield obj, ctx
        yield getattr(obj, self.ensure_identifier(member)), ctx

    def handle_quote(self, ctx, expr, *children):
        def recurse(expr):
            return [
                recurse(c) if isinstance(c, ExpressionTree) else c
                for c in expr.children
            ]
        return recurse(expr)

    def handle_def(self, ctx, expr, *children):
        value = None
        for i in range(0, len(children), 2):
            name = self.ensure_identifier(children[i])
            value = yield children[i + 1], ctx
            ctx[name] = value
        yield value, ctx

    def handle_call(self, ctx, expr, fun, *args):
        return self.evaluate_function_call(expr, ctx)

    def handle_comment(self, ctx, expr, *children):
        pass

    def handle_and(self, ctx, expr, *children):
        for child in children:
            val = yield child, ctx
            if not val:
                yield False, ctx
                break
        else:
            yield True, ctx

    def handle_or(self, ctx, expr, *children):
        for child in children:
            val = yield child, ctx
            if val:
                yield True, ctx
                break
        else:
            yield False, ctx
