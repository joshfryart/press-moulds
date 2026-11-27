import types

import numpy as np

import geometry as geo
from geometry import FormOptions, MouldOptions


def _circle(cx=0.0, cy=0.0, r=1.0, n=200):
    t = np.linspace(0, 2 * np.pi, n)
    return np.c_[cx + r * np.cos(t), cy + r * np.sin(t)]


def _result(polylines, closed, kind="explicit"):
    return types.SimpleNamespace(kind=kind, polylines=polylines, closed=closed,
                                 X=None, Y=None, Z=None)


FAST = FormOptions(size_mm=15, px=0.1)
MOULD = MouldOptions()


def test_fit_polylines_largest_bbox_dim_is_size():
    fitted = geo.fit_polylines([_circle(r=3.0)], 15)
    pts = np.vstack(fitted)
    span = (pts.max(0) - pts.min(0)).max()
    assert abs(span - 15) < 1e-6
    assert np.allclose((pts.max(0) + pts.min(0)) / 2, 0, atol=1e-9)


def test_to_svg_header():
    svg = geo.to_svg(geo.fit_polylines([_circle()], 15))
    assert svg.startswith("<svg") or svg.startswith("<?xml")


def test_build_all_circle_is_watertight_with_positive_volume():
    out = geo.build_all(_result([_circle()], [True]), FAST, MOULD)
    assert out["svg"] is not None and out["svg"].startswith("<svg")
    for key in ("form", "mould", "lid"):
        mesh = out[key]
        assert mesh.is_watertight, key
        assert mesh.volume > 0, key
    assert out["check"]["bodies"] == 1
    assert out["check"]["form_watertight"] is True
    assert out["check"]["mould_watertight"] is True


def test_stl_bytes_longer_than_header():
    out = geo.build_all(_result([_circle()], [True]), FAST, MOULD)
    data = geo.stl_bytes(out["form"])
    assert isinstance(data, bytes)
    assert len(data) > 84


def test_two_disjoint_circles_warn_separate():
    polys = [_circle(cx=-5.0, r=1.0), _circle(cx=5.0, r=1.0)]
    out = geo.build_all(_result(polys, [True, True]), FAST, MOULD)
    assert out["check"]["bodies"] == 2
    assert any("separate" in w for w in out["check"]["warnings"])


def test_build_all_empty_polylines_raises_value_error():
    try:
        geo.build_all(_result([], []), FAST, MOULD)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
