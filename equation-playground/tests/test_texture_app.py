import shutil
import pathlib

import geometry as geo
import core

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_texture_in_form_and_mould_and_validation():
    s = core.parse("x^2 + y^2 = r^2")
    r = core.sample(s, {}, None, 1200)
    base = geo.FormOptions(size_mm=30, strand_w=5.0, strand_h=2.0, px=0.1)
    tex = geo.FormOptions(size_mm=30, strand_w=5.0, strand_h=2.0, px=0.1, tex_kind="dots",
                          tex_height=0.2, tex_pitch=0.8, tex_feature=0.6)
    a = geo.build_all(r, base, geo.MouldOptions())
    b = geo.build_all(r, tex, geo.MouldOptions())
    assert b["H"].max() > a["H"].max() + 0.1
    assert b["check"]["form_watertight"] and b["check"]["mould_watertight"]
    assert b["check"]["clay_cm3"] > a["check"]["clay_cm3"]   # texture adds clay, so the cavity carries it
    import pytest
    for kw in (dict(tex_kind="nope"), dict(tex_kind="dots", tex_pitch=0.1), dict(tex_kind="dots", tex_height=3)):
        with pytest.raises(ValueError):
            geo.build_all(r, geo.FormOptions(size_mm=30, px=0.1, **kw), geo.MouldOptions())


def test_texture_surface_and_release_warning():
    s = core.parse("z = a sin(x) cos(y)")
    r = core.sample(s, {}, None, 100)
    fo = geo.FormOptions(size_mm=30, px=0.1, tex_kind="ridges", tex_height=0.2, tex_pitch=1.0)
    out = geo.build_all(r, fo, geo.MouldOptions())
    assert out["check"]["form_watertight"]
    steep = geo.FormOptions(size_mm=30, px=0.1, tex_kind="ridges", tex_height=1.0, tex_pitch=0.3, tex_feature=0.3)
    out = geo.build_all(r, steep, geo.MouldOptions())
    assert any("texture walls" in w for w in out["check"]["warnings"])


def test_app_texture_controls(tmp_path):
    from streamlit.testing.v1 import AppTest
    for f in ("app.py", "core.py", "geometry.py", "clay.py", "anim.py", "texture.py"):
        shutil.copy(ROOT / f, tmp_path / f)
    at = AppTest.from_file(str(tmp_path / "app.py"), default_timeout=120).run()
    assert not at.exception
    sel = [x for x in at.selectbox if x.key == "tex_kind"][0]
    assert sel.value == "None"
    sel.set_value("Dots").run()
    assert not at.exception
    assert at.session_state["live3d"].is_watertight
