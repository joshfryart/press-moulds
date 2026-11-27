import time

import numpy as np
import pytest

from core import EquationError, parse, sample


@pytest.mark.parametrize("eq", ["y = 9^9^9", "9^9^9^9", "x^9^9^9", "2^2^2^2^2^2", "y = 9^999999",
                                "y = 10^400", "y = x^(9^9)"])
def test_huge_numbers_rejected_fast(eq):
    t = time.time()
    with pytest.raises(EquationError):
        sample(parse(eq), {})
    assert time.time() - t < 1


def test_normal_powers_still_work():
    assert parse("y = 2^10 x").kind == "explicit"
    assert parse("y = x^1000").kind == "explicit"
    assert parse("y = 2^x").params == []


def test_unicode_sqrt_and_fractions():
    for eq in ("y = √x", "y = √(x)", "y = x½", "y = ½x"):
        assert sample(parse(eq), {}).polylines
    r = sample(parse("y = ½x"), {}, domain={"x": (0, 2)})
    assert np.allclose(r.polylines[0][:, 1], r.polylines[0][:, 0] / 2)


@pytest.mark.parametrize("eq", ["y = x​", "y = ж", "y = x＜1"])
def test_odd_unicode_errors(eq):
    with pytest.raises(EquationError):
        parse(eq)


def test_fullwidth_and_math_italic_normalised():
    assert parse("y = ｘ").params == []
    assert parse("y = 𝑥").params == []


@pytest.mark.parametrize("eq", ["y = cbrt(x)", "y = x^(1/3)"])
def test_real_cube_root_for_negative_x(eq):
    r = sample(parse(eq), {}, domain={"x": (-8, 8)})
    assert r.polylines[0][0, 1] == pytest.approx(-2.0)
    assert r.polylines[-1][-1, 1] == pytest.approx(2.0)


def test_sample_bad_arguments():
    s = parse("y = x")
    for kw in (dict(n=float("nan")), dict(domain={"x": ("a", "b")}), dict(domain={"x": (1,)})):
        with pytest.raises(EquationError):
            sample(s, {}, **kw)


@pytest.mark.parametrize("eq", ["eval(1)", "open(1)", "Symbol(a)", "eval('1')"])
def test_call_rejection_message(eq):
    with pytest.raises(EquationError) as ei:
        parse(eq)
    assert "derivative" not in str(ei.value) and "not allowed" in str(ei.value)


def test_min_empty_message():
    with pytest.raises(EquationError, match="argument"):
        parse("y = min()")


def test_floor_steps_not_joined():
    r = sample(parse("y = floor(x)"), {})
    assert len(r.polylines) >= 15
    for L in r.polylines:
        assert np.ptp(L[:, 1]) < 1e-9


@pytest.mark.parametrize("eq", ["y = ax", "y = sinx", "y = xsin(x)"])
def test_implicit_multiplication_hint(eq):
    with pytest.raises(EquationError, match=r"\*"):
        parse(eq)


def test_legit_param_names_kept():
    for eq, p in (("y = amp*x", "amp"), ("y = tau x", "tau"), ("y = k1 x", "k1")):
        assert parse(eq).params == [p]
