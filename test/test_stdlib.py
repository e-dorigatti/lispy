from lispy.interpreter import IterativeInterpreter
import pytest
from lispy.utils import parse_expr, eval_expr, load_stdlib



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

    res = eval_expr('(filter (defn even (x) (= 0 (% x 2))) (range 10))', inpr)
    assert res == [0, 2, 4, 6, 8]


def test_map():
    inpr = load_stdlib(IterativeInterpreter())

    res = eval_expr('(map (defn double (x) (* 2 x)) (range 5))', inpr)
    assert res == [0, 2, 4, 6, 8]

def test_curry():
    inpr = load_stdlib(IterativeInterpreter())
    assert eval_expr('((curry * 2) 2)', inpr) == 4
