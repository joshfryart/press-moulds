"""Fixes from the press mould assessment: thin-wall accuracy, guards, lid check, memory guard, fit=False."""
import json
import os
import types

import numpy as np
import pytest

import core
import geometry as geo
from geometry import FormOptions, MouldOptions


def _gap_H(gap_px, px, size=30):
    n = int(size / px); M = np.zeros((n, n)); kk = int(3 / px); a = int(2 / px)
    M[a:n - a, a:a + kk] = 1; M[a:n - a, a + kk + gap_px:a + 2 * kk + gap_px] = 1
    return geo.HeightMap(M)


def _strip_H(w_px, px, size=30):
    n = int(size / px); M = np.zeros((n, n)); a = int(2 / px)
    M[a:n - a, a:a + w_px] = 1
    return geo.HeightMap(M)


@pytest.mark.parametrize("px", [0.1, 0.05])
@pytest.mark.parametrize("true", [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
def test_gap_and_strip_reported_within_one_pixel(px, true):
    n = int(round(true / px))
    c = geo.check(_gap_H(n, px), px, None, None)
    assert abs(c["min_gap_mm"] - n * px) <= px + 1e-9
    c = geo.check(_strip_H(n, px), px, None, None)
    assert abs(c["min_feature_mm"] - n * px) <= px + 1e-9


def test_gap_warning_threshold_at_fine_pixel():
    px = 0.03
    lo = geo.check(_gap_H(17, px), px, None, None)           # 0.51 mm
    hi = geo.check(_gap_H(23, px), px, None, None)           # 0.69 mm
    assert any(w.startswith("resin wall") for w in lo["warnings"])
    assert not any(w.startswith("resin wall") for w in hi["warnings"])
    assert abs(lo["min_gap_mm"] - 0.51) <= px and abs(hi["min_gap_mm"] - 0.69) <= px


@pytest.mark.parametrize("px", [0.1, 0.05])
def test_half_mm_gap_warns_and_07_does_not(px):
    assert any(w.startswith("resin wall") for w in geo.check(_gap_H(int(round(0.5 / px)), px), px, None, None)["warnings"])
    assert not any(w.startswith("resin wall") for w in geo.check(_gap_H(int(round(0.7 / px)), px), px, None, None)["warnings"])


def _circle(r=10.0):
    t = np.linspace(0, 2 * np.pi, 200)
    return types.SimpleNamespace(kind="explicit", polylines=[np.c_[r * np.cos(t), r * np.sin(t)]], closed=[True],
                                 X=None, Y=None, Z=None)


def _build(fo=None, mo=None, res=None, **kw):
    fo = fo or FormOptions(size_mm=20, px=0.1)
    mo = mo or MouldOptions(pair=False, overflow=False)
    return geo.build_all(res or _circle(), fo, mo, **kw)


def test_draft_zero_and_low_warn_normal_does_not():
    assert any("draft" in w for w in _build(FormOptions(size_mm=20, px=0.1, draft_deg=0))["check"]["warnings"])
    assert any("draft" in w for w in _build(FormOptions(size_mm=20, px=0.1, draft_deg=2))["check"]["warnings"])
    assert not any("draft" in w for w in _build()["check"]["warnings"])
    with pytest.raises(ValueError, match="draft_deg"):
        _build(FormOptions(size_mm=20, px=0.1, draft_deg=-5))


def test_negative_loop_shift_is_clamped_and_warned():
    a = _build(FormOptions(size_mm=20, px=0.1, loop_shift_mm=-2.0))
    b = _build(FormOptions(size_mm=20, px=0.1, loop_shift_mm=0.0))
    assert np.array_equal(np.asarray(a["H"]), np.asarray(b["H"]))
    assert any("loop shift" in w for w in a["check"]["warnings"])
    assert not any("loop shift" in w for w in b["check"]["warnings"])


def test_strand_height_unreachable_warns_with_actual_height():
    c = _build(FormOptions(size_mm=20, px=0.05, strand_w=0.4, strand_h=1.2, draft_deg=20, loop=False))["check"]
    assert abs(c["strand_reach_mm"] - 0.55) < 0.01
    assert any("reaches only 0.55 mm of the requested 1.20" in w for w in c["warnings"])
    c = _build(FormOptions(size_mm=20, px=0.1, strand_w=1.8, strand_h=1.2, draft_deg=45, loop=False))["check"]
    assert abs(c["strand_reach_mm"] - 0.9) < 0.01
    assert any("reaches only 0.90" in w for w in c["warnings"])
    assert not any("reaches only" in w for w in _build()["check"]["warnings"])


def test_check_has_lid_watertight_and_face_counts():
    c = _build()["check"]
    assert c["lid_watertight"] is True and c["lid_faces"] > 0 and c["mould_faces"] > 0
    assert geo.check(_gap_H(10, 0.1), 0.1, None, None)["lid_watertight"] is None


def test_lid_not_watertight_warns():
    import trimesh
    open_lid = trimesh.Trimesh(np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0.]]), np.array([[0, 1, 2]]))
    c = geo.check(_gap_H(10, 0.1), 0.1, None, None, lid=open_lid)
    assert c["lid_watertight"] is False and "lid STL is not watertight" in c["warnings"]


def test_simplify_fallback_warns():
    class M:
        is_watertight = True; faces = np.zeros((10, 3)); metadata = {"simplify": dict(target=5, faces=3_700_000, fell_back=True)}
    c = geo.check(_gap_H(10, 0.1), 0.1, None, None, lid=M())
    assert any("fell back" in w for w in c["warnings"])


def test_fractal_quilt_lid_simplifies():
    d = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "fractals", "fractals.json")))[19]
    r = core.sample(core.parse(d["eq"]), {})
    out = geo.build_all(r, FormOptions(size_mm=30, px=0.05), MouldOptions(two_sided=True, pins=True, margin=6.5))
    c = out["check"]
    assert c["lid_watertight"] and c["lid_faces"] <= 1.5 * geo.MOULD_FACES
    assert not any("simplification" in w or "faces" in w for w in c["warnings"])


def test_estimate_build_gb_and_guard():
    assert geo.estimate_build_gb(30, 0.05, True, True) < 6
    assert geo.estimate_build_gb(30, 0.05) < geo.estimate_build_gb(30, 0.05, True, True)
    assert geo.estimate_build_gb(200, 0.05) > 6 and geo.estimate_build_gb(40, 0.02) > 6
    with pytest.raises(ValueError, match=r"too fine for this size: needs about .* GB, use pixel >= 0\.\d+"):
        _build(FormOptions(size_mm=40, px=0.02))
    with pytest.raises(ValueError, match="too fine"):
        _build(FormOptions(size_mm=200, px=0.05))


def test_heightmap_grid_guard():
    pm = [np.array([[0, 0], [200., 200.]])]
    with pytest.raises(ValueError, match="too fine"):
        geo.curve_heightmap(pm, [False], FormOptions(size_mm=200, px=0.02))


def test_fit_false_keeps_scale_and_fit_true_rescales():
    res = _circle(10.0)                                    # 20 mm across
    fo = FormOptions(size_mm=40, px=0.1, loop=False)
    mo = MouldOptions(pair=False, overflow=False)
    a = geo.build_all(res, fo, mo, fit=False)["check"]["form_mm"]
    b = geo.build_all(res, fo, mo, fit=True)["check"]["form_mm"]
    assert abs(a[0] - 21.8) < 0.3 and abs(b[0] - 41.8) < 0.3
    off = types.SimpleNamespace(kind="explicit", polylines=[_circle(10.0).polylines[0] + [100, -50]], closed=[True],
                                X=None, Y=None, Z=None)
    assert abs(geo.build_all(off, fo, mo, fit=False)["check"]["form_mm"][0] - a[0]) < 0.3


def test_form_mm_includes_strand_width():
    c = _build(FormOptions(size_mm=20, px=0.05, loop=False))["check"]["form_mm"]
    assert 21.5 < c[0] < 22.1


def test_two_sided_without_pins_and_thin_wall_warn():
    mo = MouldOptions(pair=False, overflow=False, two_sided=True, pins=False, wall=1.0)
    w = _build(mo=mo)["check"]["warnings"]
    assert any("no registration" in x for x in w) and any("wall 1.0 mm < 2 mm" in x for x in w)
    mo = MouldOptions(pair=False, overflow=False, two_sided=True, pins=True, wall=3.0)
    w = _build(mo=mo)["check"]["warnings"]
    assert not any("no registration" in x or "< 2 mm" in x for x in w)


def test_extreme_aspect_warns():
    t = np.linspace(0, 1, 100)
    res = types.SimpleNamespace(kind="explicit", polylines=[np.c_[t, np.exp(t) * 0.0 + 0.001 * t]], closed=[False],
                                X=None, Y=None, Z=None)
    c = geo.build_all(res, FormOptions(size_mm=30, px=0.1, loop=False), MouldOptions(pair=False, overflow=False))["check"]
    assert c["centreline_mm"][1] < 0.1
    assert any("extreme aspect" in w for w in c["warnings"])
    assert not any("extreme aspect" in w for w in _build()["check"]["warnings"])
