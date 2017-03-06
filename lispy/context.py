import builtins

from lispy.globals import GLOBALS


class ExecutionContext(object):
    def __init__(self, parent_ctx, **bindings):
        self.parent = parent_ctx
        self.bindings = bindings

    def __getitem__(self, item):
        if item in self.bindings:
            return self.bindings[item]
        elif self.parent:
            return self.parent[item]
        elif item in GLOBALS:
            return GLOBALS[item]
        elif item in builtins.__dict__:
            return builtins.__dict__[item]
        else:
            raise NameError(item)

    def __setitem__(self, key, value):
        self.bindings[key] = value

    def __contains__(self, item):
        try:
            _ = self[item]
        except (NameError, TypeError):
            return False
        else:
            return True

    def get(self, key, default=None):
        try:
            return self[key]
        except NameError:
            return default

    def __str__(self):
        return '%s --> %s' % (self.bindings, self.parent)


class MergedExecutionContext(ExecutionContext):
    def __init__(self, *contexts):
        super(MergedExecutionContext, self).__init__(None)
        self.contexts = contexts

    def __getitem__(self, item):
        for ctx in self.contexts:
            try:
                return ctx[item]
            except (NameError, KeyError):
                pass
        raise NameError(item)

    def __setitem__(self, item, value):
        self.contexts[0][item] = value

    def __contains__(self, item):
        for ctx in self.contexts:
            if item in ctx:
                return True
        return False

    def get(self, key, default=None):
        try:
            return self[key]
        except NameError:
            return default
