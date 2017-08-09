import pytest

from lispy.interpreter import IterativeInterpreter
from lispy.utils import eval_expr, load_stdlib, parse_expr


def test_inc():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(inc 0)', inpr) == 1


def test_dec():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(dec 1)', inpr) == 0


def test_first():
    inpr = load_stdlib(IterativeInterpreter())

    inpr.ctx['x'] = []
    with pytest.raises(IndexError):
        eval_expr('(first x)', inpr)

    inpr.ctx['x'] = [3, 2, 1]
    assert eval_expr('(first x)', inpr) == 3


def test_last():
    inpr = load_stdlib(IterativeInterpreter())

    with pytest.raises(IndexError):
        eval_expr('(last (list))', inpr)

    assert eval_expr('(last (list 3 2 1))', inpr) == 1


def test_rest():
    inpr = load_stdlib(IterativeInterpreter())

    assert eval_expr('(rest (list))', inpr) == []
    assert eval_expr('(rest (list 1))', inpr) == []
    assert eval_expr('(rest (list 1 2))', inpr) == [2]


def test_skip():
    inpr = load_stdlib(IterativeInterpreter())

    assert eval_expr('(skip 0 (list 1 2 3))', inpr) == [1, 2, 3]
    assert eval_expr('(skip 2 (list))', inpr) == []
    assert eval_expr('(skip 2 (list 0 1 2 3))', inpr) == [2, 3]


def test_filter():
    inpr = load_stdlib(IterativeInterpreter())

    assert eval_expr('(filter (defn even (x) (= 0 (% x 2))) (range 10))', inpr) == [0, 2, 4, 6, 8]
    assert eval_expr('(filter (defn even (x) (= 0 (% x 2))) (list))', inpr) == []


def test_map():
    inpr = load_stdlib(IterativeInterpreter())

    res = eval_expr('(map (defn double (x) (* 2 x)) (range 5))', inpr)
    assert res == [0, 2, 4, 6, 8]

def test_curry():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('((curry * 2) 2)', inpr) == 4


def test_cons():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(cons 1 (list 2 3))', inpr) == [1, 2, 3]
    assert eval_expr('(cons 1 (list))', inpr) == [1]


def test_append():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(append (list 2 3) 1)', inpr) == [2, 3, 1]
    assert eval_expr('(append (list) 1)', inpr) == [1]


def test_when():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(when (= 1 1) 1 2 3)', inpr) == 3
    assert eval_expr('(when (!= 1 1) 1 2 3)', inpr) == None


def test_unless():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(unless (= 1 1) 1)', inpr) == None
    assert eval_expr('(unless (!= 1 1) 1)', inpr) == 1


def test_zip():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(zip (list 1 2) (list 3 4 5) (list 6 7 8 9))', inpr) == [
        [1, 3, 6], [2, 4, 7]
    ]
    assert eval_expr('(zip (list) (list 1 2 3))', inpr) == []


def test_extend():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(extend (list 1 2 3) (list 4 5 6))', inpr) == [1, 2, 3, 4, 5, 6]
    assert eval_expr('(extend (list) (list 4 5 6))', inpr) == [4, 5, 6]
    assert eval_expr('(extend (list 1 2 3) (list))', inpr) == [1, 2, 3]


def test_flatten():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(flatten (list 1 2 (list 3 (list 4 (list )) 6 ) 7))', inpr) == [
        1, 2, 3, 4, 6, 7
    ]


def test_reduce():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('(reduce (# extend %0 %1) (list 1 2) (list 3 4))', inpr) == [
        1, 2, 3, 4
    ]
