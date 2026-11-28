import inspect
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pathlib

import numpy as np
import pytest

import clay
import geometry as geo

ROOT = pathlib.Path(__file__).resolve().parent.parent
HAS_FIT = "fit" in inspect.signature(geo.build_all).parameters


def _app(tmp_path, timeout=120):
    from streamlit.testing.v1 import AppTest
    for f in ("app.py", "core.py", "geometry.py", "clay.py", "anim.py"):
        shutil.copy(ROOT / f, tmp_path / f)
    return AppTest.from_file(str(tmp_path / "app.py"), default_timeout=timeout).run()


def _by_label(items, label):
    return [w for w in items if w.label == label][0]


def test_surface_note_and_loop_disabled(tmp_path):
    at = _app(tmp_path)
    assert not at.exception
    assert not _by_label(at.checkbox, "Hanging loop").disabled
    at.text_area[0].set_value("z = a sin(x) cos(y)").run()
    assert not at.exception
    assert any("normalised to Relief" in i.value for i in at.info)
    assert _by_label(at.checkbox, "Hanging loop").disabled


def test_base_and_lid_disabled_in_two_sided(tmp_path):
    at = _app(tmp_path)
    assert _by_label(at.number_input, "Base plate (mm)").disabled
    assert _by_label(at.number_input, "Lid thickness (mm)").disabled
    [r for r in at.radio if r.label == "Form type"][0].set_value("Flat back (mould + lid)").run()
    assert not _by_label(at.number_input, "Base plate (mm)").disabled
    assert not _by_label(at.number_input, "Lid thickness (mm)").disabled


def _build(at, label="Draft build"):
    _by_label(at.button, label).click().run()
    return at


@pytest.mark.skipif(not HAS_FIT, reason="geometry.build_all has no fit kwarg yet")
def test_rotation_does_not_rescale(tmp_path):
    at = _app(tmp_path)
    at.text_area[0].set_value("x = 3 cos(t), y = sin(t)").run()
    [r for r in at.radio if r.label == "Form type"][0].set_value("Flat back (mould + lid)").run()
    sizes = []
    for ang in (0.0, 45.0):
        [s for s in at.slider if s.label == "Rotate shape (deg)"][0].set_value(ang)
        _by_label(at.number_input, "Size (mm)").set_value(30.0)
        _build(at)
        assert not at.exception
        sizes.append(max(at.session_state["build"]["check"]["form_mm"][:2]))
    assert sizes[1] <= sizes[0] * 1.02


def test_base_plate_adds_clay_volume():
    H = np.full((40, 40), 1.2)
    r0 = clay.clay_balls(H, 0.5)
    r1 = clay.clay_balls(H, 0.5, base_mm=1.0)
    assert r1["base_mm3"] == pytest.approx(40 * 40 * 0.25)
    assert r1["cavity_mm3"] == pytest.approx(r0["cavity_mm3"] + 400.0)
    r2 = clay.clay_balls(H, 0.5, base_mm=1.0, two_sided=True)
    assert r2["base_mm3"] == 0.0


def test_clay_density_option():
    H = np.full((40, 40), 1.2)
    a = clay.clay_balls(H, 0.5, density=1.35)
    b = clay.clay_balls(H, 0.5, density=1.7)
    assert b["grams"] / a["grams"] == pytest.approx(1.7 / 1.35)


@pytest.mark.skipif(not hasattr(geo, "estimate_build_gb"), reason="geometry.estimate_build_gb not available yet")
def test_memory_guard_message(tmp_path):
    at = _app(tmp_path)
    _by_label(at.number_input, "Size (mm)").set_value(40.0)
    _by_label(at.number_input, "Pixel (mm)").set_value(0.02)
    if geo.estimate_build_gb(40.0, 0.02, True, True) <= 8.0:
        pytest.skip("estimate under budget")
    _build(at, "Build")
    assert not at.exception
    assert any("GB" in e.value for e in at.error)
    assert "build" not in at.session_state or at.session_state["build"] is None
