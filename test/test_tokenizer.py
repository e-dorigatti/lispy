from lispy.tokenizer import Token, Tokenizer


def test_token_split():
    parsed = list(Tokenizer().tokenize(
        'abc += 123 -3 -= -x a3 3a a&b a-b a+b a/b a*b a.b'
    ))

    assert [(t.type, t.value) for t in parsed] == [
        (Token.TOKEN_IDENTIFIER, 'abc'), (Token.TOKEN_OTHER, '+='),
        (Token.TOKEN_LITERAL, 123), (Token.TOKEN_LITERAL, -3),
        (Token.TOKEN_OTHER, '-='), (Token.TOKEN_OTHER, '-x'),
        (Token.TOKEN_IDENTIFIER, 'a3'), (Token.TOKEN_LITERAL, '3a'),
        (Token.TOKEN_IDENTIFIER, 'a'), (Token.TOKEN_OTHER, '&'),
        (Token.TOKEN_IDENTIFIER, 'b'), (Token.TOKEN_IDENTIFIER, 'a'),
        (Token.TOKEN_OTHER, '-b'), (Token.TOKEN_IDENTIFIER, 'a'),
        (Token.TOKEN_OTHER, '+b'), (Token.TOKEN_IDENTIFIER, 'a'),
        (Token.TOKEN_OTHER, '/'), (Token.TOKEN_IDENTIFIER, 'b'),
        (Token.TOKEN_IDENTIFIER, 'a'), (Token.TOKEN_OTHER, '*'),
        (Token.TOKEN_IDENTIFIER, 'b'), (Token.TOKEN_IDENTIFIER, 'a.b'),
    ]


def test_quotes():
    parsed = list(Tokenizer().tokenize('"3" 3 "\\"3\\""'))

    assert all(t.type == Token.TOKEN_LITERAL for t in parsed)
    assert [t.value for t in parsed] == [
        '3', 3, '"3"'
    ]
