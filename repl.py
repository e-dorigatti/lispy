import traceback

import click
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.token import Token
from prompt_toolkit.validation import ValidationError, Validator

from lispy.context import ExecutionContext
from lispy.expression import ExpressionTree
from lispy.interpreter import IterativeInterpreter
from lispy.tokenizer import Tokenizer
from lispy.utils import eval_expr


class ExpressionValidator(Validator):
    def validate(self, document):
        text = document.text
        try:
            tokens = Tokenizer().tokenize(text)
            _ = ExpressionTree.from_tokens(tokens)
        except SyntaxError as exc:
            raise ValidationError(message=str(exc))


def get_continuation_tokens(cli, width):
    return [(Token, '.' * (width - 1) + ' ')]


def repl(inpr, **kwargs):
    print('LISPY ver. 0.1')
    hist = InMemoryHistory()

    while True:
        try:
            text = prompt(u'>>> ', multiline=True, history=hist,
                          validator=ExpressionValidator(),
                          get_continuation_tokens=get_continuation_tokens)
        except EOFError:
            print('Quit')
            break
        except KeyboardInterrupt:
            print('Interrupted (CTRL+D to exit)')
            continue

        tokens = Tokenizer().tokenize(text)
        expressions = ExpressionTree.from_tokens(tokens)

        result = None
        try:
            for expr in expressions:
                if isinstance(expr, ExpressionTree):
                    result = inpr.evaluate(expr)
                else:
                    result = expr
        except:
            inpr.print_stacktrace()
            traceback.print_exc()
        else:
            print(result)


@click.command()
@click.argument('input-file', type=click.File('r'), nargs=-1)
@click.option('-e', '--expression')
@click.option('--without-stdlib', '-S', is_flag=True)
def main(input_file, expression, without_stdlib, **kwargs):
    inpr = IterativeInterpreter(with_stdlib=not without_stdlib)

    if input_file:
        for f in input_file:
            eval_expr(f.read(), inpr)
    elif expression:
        res = eval_expr(expression, inpr)
        print(res)
    else:
        repl(inpr, **kwargs)


if __name__ == '__main__':
    main()
