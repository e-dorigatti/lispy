from functools import reduce
from lispy.expression import ExpressionTree

GLOBALS = {}


def glob(name):
    def wrapper(func):
        assert name not in GLOBALS, 'global redefined'
        GLOBALS[name] = func
        return func
    return wrapper


@glob('+')
def sum_(*args):
    acc = args[0]
    for each in args[1:]:
        acc += each
    return acc


@glob('-')
def subtr_(*args):
    acc = args[0]
    for each in args[1:]:
        acc -= each
    return acc


@glob('*')
def mult(*args):
    return reduce(lambda x, y: x * y, args)


@glob('/')
def division(*args):
    acc = args[0]
    for each in args[1:]:
        acc /= each
    return acc


@glob('=')
def equality(*args):
    prev = args[0]
    for each in args[1:]:
        if each != prev:
            return False
        prev = each
    return True


@glob('!=')
def not_equality(*args):
    return not equality(*args)


@glob('%')
def mod(a, b):
    return a % b


@glob('<')
def lessthan(*args):
    return all(x < y for x, y in zip(args[:-1], args[1:]))


@glob('<=')
def lesseqthan(*args):
    return all(x <= y for x, y in zip(args[:-1], args[1:]))


@glob('>')
def greaterthan(*args):
    return all(x > y for x, y in zip(args[:-1], args[1:]))


@glob('>=')
def greatereqthan(*args):
    return all(x >= y for x, y in zip(args[:-1], args[1:]))


@glob('print')
def print_(*args):
    parts = []
    for each in args:
        if isinstance(each, list):
            parts.append(ExpressionTree.to_string(each))
        else:
            parts.append(str(each))
    print(' '.join(parts))


@glob('readline')
def readline(*args):
    return raw_input(' '.join(args))


@glob('int')
def to_int(x, base=10):
    return int(x, base)


@glob('float')
def to_float(x):
    return float(x)


@glob('str')
def to_string(obj):
    return str(obj)


@glob('nth')
def nth(lst, i):
    return lst[i]


@glob('slice')
def slice_(lst, start, end, step=1):
    return lst[start:end:step]


@glob('list')
def make_list(*args):
    return list(args)


@glob('dict')
def make_dict(*args):
    return dict(zip(args[::2], args[1::2]))


@glob('apply')
def apply_function(function, *args):
    return function(*args)


@glob('not')
def negate(thing):
    return not thing


@glob('range')
def range_list(*args):
    return list(range(*args))
