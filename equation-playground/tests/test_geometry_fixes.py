import types

import numpy as np
import pytest

import core
import geometry as geo
from geometry import FormOptions, MouldOptions


def _curve(eq, params=None, size=40, px=0.1, loop=True):
    r = core.sample(core.parse(eq), params or {})
    fo = FormOptions(size_mm=size, px=px, loop=loop)
    pm = geo.fit_polylines(r.polylines, size)
    H, _ = geo.curve_heightmap(pm, r.closed, fo)
    return H, fo


@pytest.mark.parametrize("eq,params", [
    ("y = x", {}), ("y = 1 + 0*x", {}), ("x = 1 + 0*y", {}), ("y = 0.5*x", {}),
    ("r = a + b cos(k theta)", {"a": 0, "b": 0}),
])
@pytest.mark.parametrize("px", [0.1, 0.05])
@pytest.mark.parametrize("loop", [True, False])
def test_straight_lines_form_watertight(eq, params, px, loop):
    H, fo = _curve(eq, params, 40, px, loop)
    assert geo.form_mesh(H, px).is_watertight


@pytest.mark.parametrize("eq", ["y = x^2", "y = |x|"])
def test_auto_loop_is_at_top(eq):
    H, _ = _curve(eq)
    ii, _ = np.nonzero(np.asarray(H) > 0)
    r, _ = H.info["loop_ctr_px"]
    ring_top = r + H.info["loop_od"] / 2 / 0.1
    assert ring_top >= ii.max() - 2           # ring reaches the top of the form
    assert r > geo._com(np.asarray(H), 0, 0, 1)[1]   # and sits above the centre of mass


def _strip_H(w, px, gap=None):
    n = int(40 / px); M = np.zeros((n, n))
    k = max(1, int(round(w / px)))
    if gap is None:
        M[10:n - 10, 50:50 + k] = 1
    else:
        kk = int(3 / px); g = int(round(gap / px))
        M[10:n - 10, 50:50 + kk] = 1; M[10:n - 10, 50 + kk + g:50 + 2 * kk + g] = 1
    return geo.HeightMap(M)


@pytest.mark.parametrize("px", [0.1, 0.05])
@pytest.mark.parametrize("w", [0.1, 0.15, 0.2])
def test_check_warns_thin_strip(px, w):
    c = geo.check(_strip_H(w, px), px, None, None)
    assert c["min_feature_mm"] < 0.5
    assert any(x.startswith("feature") for x in c["warnings"])


@pytest.mark.parametrize("px", [0.1, 0.05])
@pytest.mark.parametrize("g", [0.1, 0.15, 0.2])
def test_check_warns_thin_gap(px, g):
    c = geo.check(_strip_H(0, px, g), px, None, None)
    assert c["min_gap_mm"] < 0.6
    assert any(x.startswith("resin wall") for x in c["warnings"])


def test_check_thick_feature_no_warning_and_empty_form_none():
    c = geo.check(_strip_H(2.0, 0.1), 0.1, None, None)
    assert not any(x.startswith("feature") for x in c["warnings"])
    c = geo.check(geo.HeightMap(np.zeros((20, 20))), 0.1, None, None)
    assert c["min_feature_mm"] is None        # empty form: no 6.0 placeholder


def _circle():
    t = np.linspace(0, 2 * np.pi, 100)
    return types.SimpleNamespace(kind="explicit", polylines=[np.c_[np.cos(t), np.sin(t)]], closed=[True],
                                 X=None, Y=None, Z=None)


@pytest.mark.parametrize("fo", [
    dict(size_mm=0), dict(size_mm=-5), dict(px=0), dict(px=-0.1), dict(px=float("nan")),
    dict(strand_w=0), dict(loop_h=0), dict(loop_h=-1),
])
def test_bad_form_options_raise_valueerror(fo):
    with pytest.raises(ValueError):
        geo.build_all(_circle(), FormOptions(**{"size_mm": 15, "px": 0.1, **fo}), MouldOptions())


@pytest.mark.parametrize("mo", [dict(wall=0), dict(wall=-1), dict(chamfer=0), dict(chamfer=-1),
                                dict(pins=True, pin_d=0), dict(pins=True, pin_d=-1)])
def test_bad_mould_options_raise_valueerror(mo):
    with pytest.raises(ValueError):
        geo.build_all(_circle(), FormOptions(size_mm=15, px=0.1), MouldOptions(**mo))


def test_loop_h_zero_ok_when_loop_off_and_pin_d_zero_ok_without_pins():
    # a zero is legitimate when the feature is switched off
    geo.build_all(_circle(), FormOptions(size_mm=15, px=0.1, loop=False, loop_h=0), MouldOptions(pin_d=0))


def test_nan_in_heightmap_raises():
    H = np.ones((10, 10)); H[3, 3] = np.nan
    with pytest.raises(ValueError):
        geo.form_mesh(H, 0.1)
    with pytest.raises(ValueError):
        geo.mould_mesh(H, MouldOptions(), 0.1)
    with pytest.raises(ValueError):
        geo.check(H, 0.1, None, None)
