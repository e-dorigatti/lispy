class Token:
    TOKEN_EXPR_BEGIN = 1
    TOKEN_EXPR_END = 2
    TOKEN_LITERAL = 3
    TOKEN_IDENTIFIER = 4
    TOKEN_OTHER = 5

    TOKEN_IDENTIFIER_START = ('abcdefghijklmnopqrstuvwxyz' +
                              'ABCDEFGHIJKLMNOPQRSTUVWXYZ_')
    TOKEN_LITERAL_START = '".0123456789'

    def __init__(self, value, type_=None):
        self.value = value
        self.type = type_ or Token.guess_token_type(value[0])

    @staticmethod
    def guess_token_type(initial_char):
        if initial_char in Token.TOKEN_LITERAL_START:
            return Token.TOKEN_LITERAL
        elif initial_char in Token.TOKEN_IDENTIFIER_START:
            return Token.TOKEN_IDENTIFIER
        elif initial_char == '(':
            return Token.TOKEN_EXPR_BEGIN
        elif initial_char == ')':
            return Token.TOKEN_EXPR_END
        else:
            return Token.TOKEN_OTHER

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "'%s" % self.value

    def __eq__(self, other):
        return (isinstance(other, Token)
                and other.value == self.value
                and other.type == self.type)


class Tokenizer:

    # create a new token if these characters appear
    # before/after an alphanumeric character
    TOKEN_SPLIT_BEFORE = '*&=/<>'
    TOKEN_SPLIT_AFTER = '-+*/&=><'


    def tokenize(self, string):
        cur_token = None
        inside_quotes = False
        prev_char = None

        for char in string:
            new_type = None     # set to start a new token from this char
            singleton = False   # true if the new token contains only this char

            if char == '(':
                new_type = Token.TOKEN_EXPR_BEGIN
                singleton = True
            elif char == ')':
                new_type = Token.TOKEN_EXPR_END
                singleton = True
            elif char == '"' and not inside_quotes:
                new_type = Token.TOKEN_LITERAL
                inside_quotes = True
            elif char == '"' and inside_quotes and prev_char != '\\':
                new_type = -1
                inside_quotes = False
                cur_token.value += '"'
            elif char.isspace() and not inside_quotes:
                new_type = -1

            elif (cur_token
                  and ((cur_token.value[-1].isalnum() and char in self.TOKEN_SPLIT_AFTER)
                      or cur_token.value[-1] in self.TOKEN_SPLIT_BEFORE and char.isalnum())
                  and not inside_quotes):

                new_type = Token.guess_token_type(char)
            elif not cur_token:
                new_type = Token.guess_token_type(char)

            if new_type is not None:
                if cur_token:
                    succ, val = self.tryparse(cur_token.value)
                    cur_token.value = val
                    if succ:
                        cur_token.type = Token.TOKEN_LITERAL
                    yield cur_token

                if new_type >= 0:
                    cur_token = Token(char, new_type)
                    if singleton:
                        yield cur_token
                        cur_token = None
                else:
                    cur_token = None
            elif cur_token:
                cur_token.value += char

            prev_char = char

        if cur_token is not None:
            succ, val = self.tryparse(cur_token.value)
            cur_token.value = val
            if succ:
                cur_token.type = Token.TOKEN_LITERAL
            yield cur_token

    def tryparse(self, value):
        try:
            return True, int(value)
        except ValueError:
            pass

        try:
            return True, float(value)
        except ValueError:
            pass

        if value == 'true':
            return True, True
        elif value == 'false':
            return True, False
        elif value[0] == '"' and value[-1] == '"':
            return True, self.unescape(value[1:-1])
        else:
            return False, value

    def unescape(self, string):
        return (string
                .replace('\\"', '"')
                .replace('\\n', '\n')
                .replace('\\t', '\t')
                .replace('\\r', '\r'))
