from lispy.tokenizer import Tokenizer
from lispy.context import ExecutionContext
from lispy.expression import ExpressionTree


def parse_expr(program):
    tokens = Tokenizer().tokenize(program)
    return ExpressionTree.from_tokens(tokens)


def eval_expr(program, inpr=None):
    program = parse_expr(program)

    result = None
    for expression in program:
        result = inpr.evaluate(expression)
    return result


def load_stdlib(inpr):
    with open('lispy/stdlib.lispy') as f:
        eval_expr(f.read(), inpr)
    return inpr

