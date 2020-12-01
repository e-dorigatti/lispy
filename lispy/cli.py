import traceback

import click

from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.validation import ValidationError, Validator

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


def get_continuation_tokens(width, line_number, is_soft_wrap):
    return [('', '.' * (width - 1) + ' ')]


def repl(inpr, **kwargs):

    print('LISPY ver. 0.1')
    print('Alt+Enter to evaluate an expression')
    hist = InMemoryHistory()

    while True:
        try:
            text = prompt(u'>>> ', multiline=True, history=hist,
                          validator=ExpressionValidator(),
                          prompt_continuation=get_continuation_tokens)
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
            continue

        if isinstance(result, list):
            print(ExpressionTree.to_string(result))
        else:
            print(result)


@click.command()
@click.argument('input-file', type=click.File('r'), nargs=-1)
@click.option('-e', '--expression', help='Evaluate this expression and print the result')
@click.option('--without-stdlib', '-S', is_flag=True, help='Do not load standard library at startup.')
@click.option('--do-repl', '-r', is_flag=True, help='Start the REPL after evaluating the file and/or the expression')
def main(input_file, expression, without_stdlib, do_repl, **kwargs):
    '''
    Python-based LISP interpreter.

    Starts the REPL when invoked without arguments. Otherwise, executes the code in
    the file (if given), then executes the provided expression (if given), then
    enters the REPL (if the flag is specified).
    '''
    inpr = IterativeInterpreter(with_stdlib=not without_stdlib)

    if input_file:
        for f in input_file:
            eval_expr(f.read(), inpr)

    if expression:
        result = eval_expr(expression, inpr)

        if isinstance(result, list):
            print(ExpressionTree.to_string(result))
        else:
            print(result)

    if do_repl or (not expression and not input_file):
        repl(inpr, **kwargs)


if __name__ == '__main__':
    main()
