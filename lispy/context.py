from lispy.excs import NameNotFoundException
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
            raise NameNotFoundException(item)

    def __setitem__(self, key, value):
        self.bindings[key] = value

    def __contains__(self, item):
        try:
            _ = self[item]
        except (NameNotFoundException, TypeError):
            return False
        else:
            return True

    def get(self, key, default=None):
        try:
            return self[key]
        except NameNotFoundException:
            return default

    def __str__(self):
        return '%s --> %s' % (self.bindings, self.parent)

