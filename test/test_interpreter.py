import pytest

from lispy.context import ExecutionContext
from lispy.interpreter import IterativeInterpreter
from lispy.utils import eval_expr, parse_expr
from lispy.globals import GLOBALS
from lispy.tokenizer import Token


def test_balanced_parentheses():
    parse_expr('(()()((())())())')

    with pytest.raises(SyntaxError):
        parse_expr('(((())')

    with pytest.raises(SyntaxError):
        parse_expr('(())))')


def test_operations():
    inpr = IterativeInterpreter()
    assert eval_expr('(+ 1 1)', inpr) == 2
    assert eval_expr('(- 1 1)', inpr) == 0
    assert eval_expr('(/ 2 1)', inpr) == 2
    assert eval_expr('(* 2 2)', inpr) == 4


def test_nested_call():
    inpr = IterativeInterpreter()
    assert eval_expr('(+ (+ 1 1) 1)', inpr) == 3


def test_conditional():
    inpr = IterativeInterpreter()
    assert eval_expr('(if (= 0 (- 1 1)) 1 -1)', inpr) == 1


def test_let():
    inpr = IterativeInterpreter()
    assert eval_expr('(let (x 1 y 3) (+ x y))', inpr) == 4


def test_defn():
    inpr = IterativeInterpreter()
    assert eval_expr('(defn double (x) (+ x x)) (double 2)', inpr) == 4
    assert 'double' in inpr.ctx


def test_do():
    inpr = IterativeInterpreter()
    assert eval_expr('(do (+ 1 1) (- 1 1))', inpr) == 0

    assert eval_expr('(do (defn inc (x) (+ x 1)) (inc 1))', inpr) == 2
    assert 'inc' in inpr.ctx

    assert eval_expr('(do 3 & (list (+ 1 1) (- 1 1)))', inpr) == 0


def test_recursion():
    inpr = IterativeInterpreter()
    assert eval_expr(
        '(defn fact (x) (if (< x 2) 1 (* x (fact (- x 1))))) (fact 4)',
        inpr
    ) == 24


def test_varargs():
    inpr = IterativeInterpreter()
    assert eval_expr('(defn sum (& args) (+ &args)) (sum 1 2 3 4)', inpr) == 10
    assert eval_expr('(defn f (x y z) (+ x y z)) (f 1 & (list 2 3))', inpr) == 6


def test_import():
    inpr = IterativeInterpreter()
    eval_expr('(pyimport json)', inpr)

    import json
    assert inpr.ctx.get('json') == json
    assert eval_expr('(json.loads "[1, 2, 3]")', inpr) == [1, 2, 3]


def test_import_from():
    inpr = IterativeInterpreter()
    eval_expr('(pyimport_from json.decoder JSONArray)', inpr)

    from json.decoder import JSONArray
    assert inpr.ctx.get('JSONArray') == JSONArray


def test_member():
    ctx = ExecutionContext(None)
    ctx['s'] = '  abc  '
    inpr = IterativeInterpreter(ctx)
    assert eval_expr(r'(. strip s)', inpr) == ctx['s'].strip


def test_def():
    inpr = IterativeInterpreter()
    assert eval_expr('(def x 1 y (+ x 1))', inpr) == 2
    assert 'x' in inpr.ctx and 'y' in inpr.ctx
    assert eval_expr('(+ x y)', inpr) == 3


def test_str_names():
    inpr = IterativeInterpreter()
    with pytest.raises(NameError):
        eval_expr('(+ x y)', inpr)


def test_call():
    inpr = IterativeInterpreter()
    assert eval_expr('((. strip " abc "))', inpr) == 'abc'


def test_and():
    inpr = IterativeInterpreter()
    eval_expr('(def calls (list)) (defn canary (x) (do ((. append calls) x) x))', inpr)
    assert not eval_expr('(and (canary 0) (canary 1) (canary 2))', inpr)
    assert inpr.ctx['calls'] == [0]

    assert not eval_expr('(and 1 & (list 2 0 3))', inpr)


def test_or():
    inpr = IterativeInterpreter()
    eval_expr('(def calls (list)) (defn canary (x) (do ((. append calls) x) x))', inpr)
    assert eval_expr('(or (canary 0) (canary 1) (canary 2))', inpr)
    assert inpr.ctx['calls'] == [0, 1]

    assert eval_expr('(or 0 & (list 0 2 3))', inpr)


def test_anonymous_functions():
    inpr = IterativeInterpreter()
    assert eval_expr('((# * %0 2) 2)', inpr) == 4


def test_quote():
    inpr = IterativeInterpreter()

    def t(val):
        return Token(val, Token.guess_token_type(str(val)[0]))

    assert eval_expr('(quote + 1 2)', inpr) == [t('+'), t(1), t(2)]
    assert eval_expr('(quote 1 2 (3 (4 5) 6) 7)', inpr) == [
        t(1), t(2), [t(3), [t(4), t(5)], t(6)], t(7)
    ]
    assert eval_expr('(quote + 1 ~(+ 1 1))', inpr) == [t('+'), t(1), 2]

    with pytest.raises(RuntimeError):
        eval_expr('(+ ~(= 1 0) 2)', inpr)


def test_macro():
    inpr = IterativeInterpreter()
    eval_expr('(defmacro infix (args) (list (nth args 1) (nth args 0) (nth args 2)))', inpr)

    assert eval_expr('(macroexpand infix (1 + 1))', inpr) == [
        Token('+', Token.TOKEN_OTHER), Token(1, Token.TOKEN_LITERAL), Token(1, Token.TOKEN_LITERAL)
    ]

    assert eval_expr('(infix (1 + 1))', inpr) == 2


def test_dynamic_bindings():
    inpr = IterativeInterpreter()
    assert eval_expr('(defn f (x) (+ x y)) (let (y 1) (f 2))', inpr) == 3
