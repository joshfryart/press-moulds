import numpy as np
import pytest

import core
from core import EquationError, parse, sample


def _finite_polylines(res):
    assert res.polylines, "expected at least one polyline"
    for pl in res.polylines:
        assert pl.ndim == 2 and pl.shape[1] == 2
        assert pl.shape[0] >= 2
        assert np.isfinite(pl).all()


# ---------------------------------------------------------------- parse: kind and params

def test_explicit_sin_params():
    s = parse("y = a*sin(b*x)")
    assert s.kind == "explicit"
    assert s.params == ["a", "b"]
    assert s.defaults == {"a": 1.0, "b": 1.0}
    assert s.domain == {"x": (-10.0, 10.0)}


def test_explicit_power_no_equals():
    s = parse("a x^2 + b")
    assert s.kind == "explicit"
    assert s.params == ["a", "b"]
    assert s.domain == {"x": (-10.0, 10.0)}


def test_implicit_circle_param_r():
    s = parse("x^2 + y^2 = r^2")
    assert s.kind == "implicit"
    assert s.params == ["r"]
    assert s.domain == {"x": (-10.0, 10.0), "y": (-10.0, 10.0)}


def test_parametric_params():
    s = parse("x = a*cos(t), y = b*sin(k*t)")
    assert s.kind == "parametric"
    assert s.params == ["a", "b", "k"]
    assert s.domain == {"t": (0.0, 2 * np.pi)}


def test_polar_params():
    s = parse("r = a*cos(k*theta)")
    assert s.kind == "polar"
    assert s.params == ["a", "k"]
    assert s.domain == {"theta": (0.0, 2 * np.pi)}


def test_surface_params():
    s = parse("z = a*sin(x)*cos(y)")
    assert s.kind == "surface"
    assert s.params == ["a"]
    assert set(s.domain) == {"x", "y"}


# ---------------------------------------------------------------- sample

def test_explicit_sample_is_finite_polyline():
    res = sample(parse("y = a*sin(b*x)"), {"a": 1.0, "b": 1.0}, n=800)
    assert res.kind == "explicit"
    _finite_polylines(res)
    for pl in res.polylines:
        assert pl.shape[1] == 2


def test_tan_has_multiple_polylines():
    res = sample(parse("y = tan(x)"), {}, n=800)
    assert len(res.polylines) > 1
    _finite_polylines(res)


def test_sqrt_has_no_negative_x():
    res = sample(parse("y = sqrt(x)"), {}, n=800)
    _finite_polylines(res)
    xs = np.concatenate([pl[:, 0] for pl in res.polylines])
    assert (xs >= 0).all()


def test_surface_grids_have_equal_shape():
    res = sample(parse("z = a*sin(x)*cos(y)"), {"a": 2.0})
    assert res.polylines == []
    assert res.X is not None and res.Y is not None and res.Z is not None
    assert res.X.shape == res.Y.shape == res.Z.shape


def test_changing_param_doubles_amplitude():
    spec = parse("y = a*sin(x)")
    r1 = sample(spec, {"a": 1.0}, n=800)
    r2 = sample(spec, {"a": 2.0}, n=800)
    y1 = np.concatenate([pl[:, 1] for pl in r1.polylines])
    y2 = np.concatenate([pl[:, 1] for pl in r2.polylines])
    assert np.max(np.abs(y2)) == pytest.approx(2 * np.max(np.abs(y1)), rel=1e-6)


def test_implicit_circle_radius_follows_param():
    spec = parse("x^2 + y^2 = r^2")
    res = sample(spec, {"r": 3.0}, n=800)
    _finite_polylines(res)
    pts = np.vstack(res.polylines)
    assert np.hypot(pts[:, 0], pts[:, 1]).max() == pytest.approx(3.0, abs=0.1)


# ---------------------------------------------------------------- errors

@pytest.mark.parametrize("text", ["", "   ", "y = = 3", "__import__('os')"])
def test_equation_error(text):
    with pytest.raises(EquationError):
        parse(text)


def test_error_type_is_value_error():
    assert issubclass(EquationError, ValueError)
    assert core.EquationError is EquationError
