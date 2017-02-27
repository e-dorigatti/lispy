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

        ctx = ExecutionContext(self.ctx, **bindings)
        yield self.body, ctx

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
        self.body = ExpressionTree(children)
        self.ctx = ctx

    def __call__(self, *args):
        ctx = ExecutionContext(self.ctx)
        for i, x in enumerate(args):
            ctx['%' + str(i)] = x
        yield self.body, ctx

    def __eq__(self, other):
        return False

    def __str__(self):
        return '<anonymous function>'


class IterativeInterpreter:
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

            name = expr.children[0].value.replace('.', 'dot').replace('#', 'hash')
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
        formal = [self.ensure_identifier(t) if t.value != '&' else '&'
                  for t in parameters.children]
        f = Function(self.ensure_identifier(name), formal, body, ctx)

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

    def handle_hash(self, ctx, expr, *children):
        yield AnonymousFunction(ctx, children), ctx
