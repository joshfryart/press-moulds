import pathlib
import shutil

import numpy as np
import pytest

import clay

ROOT = pathlib.Path(__file__).resolve().parent.parent


def slab(size_mm, px=0.5, h=1.2):
    n = int(size_mm / px)
    return np.full((n, n), h)


def test_auto_respects_cap_and_warns():
    r = clay.clay_balls(slab(200), 0.5)
    assert r["n"] <= clay.MAX_AUTO_BALLS
    assert r["d_mm"] > 7.0 and r["warning"]


def test_no_warning_for_normal_form():
    r = clay.clay_balls(slab(30), 0.5)
    assert r["warning"] is None and r["d_mm"] <= 7.0


@pytest.mark.parametrize("kw", [dict(extra_pct=-200), dict(extra_pct=-100), dict(extra_pct=float("nan")),
                                dict(px=-0.05), dict(px=0), dict(px=float("nan"))])
def test_bad_values_raise_valueerror(kw):
    args = dict(px=0.5, extra_pct=15.0)
    args.update(kw)
    with pytest.raises(ValueError):
        clay.clay_balls(slab(20), **args)


@pytest.mark.parametrize("H", [np.zeros((10, 10)), np.zeros((0, 0)), np.zeros((0, 5))])
def test_empty_form(H):
    with pytest.raises(ValueError):
        clay.clay_balls(H, 0.5)


def test_n_larger_than_pixels():
    H = np.zeros((10, 10))
    H[2, 3] = H[5, 5] = 1.0
    r = clay.clay_balls(H, 0.5, n=12)
    assert r["n"] == 2 and len(r["balls"]) == 2


def test_app_range_warning_and_no_crash(tmp_path):
    from streamlit.testing.v1 import AppTest
    for f in ("app.py", "core.py", "geometry.py", "clay.py"):
        shutil.copy(ROOT / f, tmp_path / f)
    at = AppTest.from_file(str(tmp_path / "app.py"), default_timeout=60).run()
    assert not at.exception
    ni = [n for n in at.number_input if n.label.endswith(" min") and n.key and n.key.startswith("dom_")]
    assert ni
    hi = [n for n in at.number_input if n.key == ni[0].key.replace("_lo", "_hi")][0]
    ni[0].set_value(hi.value + 1.0).run()
    assert not at.exception
    assert any("min must be below max" in w.value for w in at.warning)


def test_app_bad_equation_clean_message(tmp_path):
    from streamlit.testing.v1 import AppTest
    for f in ("app.py", "core.py", "geometry.py", "clay.py"):
        shutil.copy(ROOT / f, tmp_path / f)
    at = AppTest.from_file(str(tmp_path / "app.py"), default_timeout=60).run()
    at.text_area[0].set_value("y = 10^400 x").run()
    assert not at.exception
    for e in at.error:
        assert "OverflowError" not in e.value and "int too large" not in e.value
