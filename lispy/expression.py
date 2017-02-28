from lispy.tokenizer import Token, Tokenizer


class ExpressionTree:
    def __init__(self, children=None):
        self.children = children or []

    @staticmethod
    def from_tokens(token_stream):
        class CheckBalancedParentheses:
            def __init__(self):
                self.open_pars = self.closed_pars = 0

            def parse(self, tokens):
                expressions = []
                for token in tokens:
                    if token.type == Token.TOKEN_EXPR_BEGIN:
                        self.open_pars += 1
                        children = self.parse(tokens)
                        expressions.append(ExpressionTree(children))
                    elif token.type == Token.TOKEN_EXPR_END:
                        self.closed_pars += 1
                        break
                    else:
                        expressions.append(token)

                return expressions

        check = CheckBalancedParentheses()
        exprs = check.parse(iter(token_stream))
        if check.open_pars != check.closed_pars:
            raise SyntaxError('unbalanced parentheses (open: %s closed: %s)'
                              '' % (check.open_pars, check.closed_pars))
        else:
            return exprs

    def print_indent(self, indent=0):
        ind = '  '
        text = ['%s%s(' % (ind * indent, self.__class__.__name__)]
        for child in self.children:
            if isinstance(child, ExpressionTree):
                text.append(child.print_indent(indent + 1))
            else:
                text.append(ind * (indent + 1) + child.__str__())
        text.append(ind * indent + ')')
        return '\n'.join(text)

    def print_short(self):
        parts = []
        for child in self.children:
            if isinstance(child, ExpressionTree):
                parts.append('(' + ' '.join(
                    '(...)' if isinstance(c, ExpressionTree) else str(c)
                    for c in child.children
                ) + ')')
            else:
                parts.append(str(child))
        return '(%s)' % ' '.join(parts)

    def __str__(self):
        return '(' + ' '.join(child.__str__() for child in self.children) + ')'
