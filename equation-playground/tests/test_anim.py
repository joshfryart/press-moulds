import numpy as np
import plotly.graph_objects as go
import pytest

import anim
import core


def make_fig(res):
    fig = go.Figure()
    if res.kind == "surface":
        fig.add_trace(go.Surface(x=res.X, y=res.Y, z=res.Z))
    else:
        for pl in res.polylines:
            fig.add_trace(go.Scatter(x=pl[:, 0], y=pl[:, 1], mode="lines"))
    return fig


def res(text, **p):
    spec = core.parse(text)
    return spec, core.sample(spec, p, None, 200)


def test_same_result_not_animated():
    _, a = res("y = a sin(x)", a=1)
    _, b = res("y = a sin(x)", a=1)
    fig, animated = anim.morph_figure(make_fig, b, a)
    assert not animated and not fig.frames


def test_param_change_morphs_curve():
    _, a = res("y = a sin(x)", a=1)
    _, b = res("y = a sin(x)", a=2)
    fig, animated = anim.morph_figure(make_fig, b, a)
    assert animated and len(fig.frames) == anim.MORPH_STEPS
    # final frame is the exact new curve
    last = fig.frames[-1].data[0]
    assert np.allclose(last.y, b.polylines[0][:, 1])
    # first frame sits between old and new
    mid = np.asarray(fig.frames[0].data[0].y)
    assert mid.max() < 2.0 and mid.max() > 1.0 - 1e-9


def test_no_prev_or_kind_change_or_count_change():
    _, a = res("y = sin(x)")
    assert anim.morph_figure(make_fig, a, None)[1] is False
    _, c = res("r = 1 + cos(theta)")
    assert anim.morph_figure(make_fig, c, a)[1] is False
    _, t = res("y = tan(x)")  # several pieces
    assert anim.morph_figure(make_fig, t, a)[1] is False


def test_surface_morph():
    _, a = res("z = a sin(x) cos(y)", a=1)
    _, b = res("z = a sin(x) cos(y)", a=2)
    fig, animated = anim.morph_figure(make_fig, b, a)
    assert animated and len(fig.frames) == anim.MORPH_STEPS


def test_html_has_frames():
    _, a = res("y = a x", a=1)
    _, b = res("y = a x", a=2)
    fig, animated = anim.morph_figure(make_fig, b, a)
    html = anim.to_html(fig, animated)
    assert "Plotly.addFrames" in html and "animate" in html


def test_sweep_curve_and_surface():
    spec, _ = res("y = a sin(x)", a=1)
    fig, n = anim.sweep_figure(make_fig, spec, {"a": 1}, None, 200, "a", -2, 2, 15)
    assert n == 15 and len(fig.layout.sliders[0].steps) == 15
    spec, _ = res("z = a sin(x) cos(y)", a=1)
    fig, n = anim.sweep_figure(make_fig, spec, {"a": 1}, None, 200, "a", 0, 3, 10)
    assert n == 10


def test_sweep_varying_piece_count():
    spec, _ = res("y = tan(a x)", a=1)
    fig, n = anim.sweep_figure(make_fig, spec, {"a": 1}, None, 400, "a", 0.5, 3, 8)
    k = max(len(f.data) for f in fig.frames)
    assert all(len(f.data) == k for f in fig.frames) and len(fig.data) == k


def test_sweep_nothing_to_draw():
    spec, _ = res("y = sqrt(a) * x", a=1)
    with pytest.raises(ValueError):
        anim.sweep_figure(make_fig, spec, {"a": 1}, None, 100, "a", -3, -1, 5)
