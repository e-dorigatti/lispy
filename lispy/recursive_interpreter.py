import inspect

import importlib


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
        return self.evaluate(ctx)

    def __eq__(self, other):
        if not isinstance(other, Function):
            return False
        return (self.name == other.name and
                self.parameters == other.parameters and
                self.body == other.body)

    def __str__(self):
        return '<function "%s">' % self.name
    
    def evaluate(self, ctx):
        raise NotImplemented


class RecursiveInterpreter:
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
                raise SyntaxError('expected syntax: (%s %s)' % (
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
