"""Animation helpers: morph between two plots, and sweep one parameter."""
import math

import numpy as np
import plotly.graph_objects as go

import core

MAX_PTS = 1500          # points per polyline while morphing
GRID_TARGET = 60        # surface grid size used for in-between frames
MORPH_STEPS = 12
FRAME_MS = 30
PLAY = dict(frame=dict(duration=FRAME_MS, redraw=True), transition=dict(duration=0), fromcurrent=True)


def _smooth(t):
    return t * t * (3 - 2 * t)


def _resample(pl, m):
    pl = np.asarray(pl, float)
    seg = np.hypot(*np.diff(pl, axis=0).T)
    d = np.r_[0.0, np.cumsum(seg)]
    if d[-1] <= 0:
        return np.repeat(pl[:1], m, axis=0)
    t = np.linspace(0.0, d[-1], m)
    return np.c_[np.interp(t, d, pl[:, 0]), np.interp(t, d, pl[:, 1])]


def _bounds(polys):
    pts = np.vstack(polys)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    pad = 0.06 * max(float((hi - lo).max()), 1e-9)
    return lo - pad, hi + pad


def _stride(shape):
    return max(1, math.ceil(max(shape) / GRID_TARGET))


def same(a, b):
    """True if two Results draw the same picture."""
    if a is None or b is None or a.kind != b.kind:
        return False
    if a.kind == "surface":
        return (a.Z.shape == b.Z.shape and np.array_equal(a.Z, b.Z, equal_nan=True)
                and np.array_equal(a.X, b.X, equal_nan=True) and np.array_equal(a.Y, b.Y, equal_nan=True))
    if len(a.polylines) != len(b.polylines):
        return False
    return all(p.shape == q.shape and np.array_equal(p, q) for p, q in zip(a.polylines, b.polylines))


def morph_figure(make_fig, new, prev):
    """Figure for `new`. If `prev` is a compatible earlier plot, the figure animates prev -> new
    (frames autoplay when rendered with auto_play). Returns (fig, animated)."""
    fig = make_fig(new)
    if prev is None or prev.kind != new.kind or same(prev, new):
        return fig, False
    if new.kind == "surface":
        return _morph_surface(fig, new, prev)
    if not new.polylines or len(prev.polylines) != len(new.polylines):
        return fig, False
    return _morph_curves(fig, new, prev)


def _morph_curves(fig, new, prev):
    m = int(min(MAX_PTS, max(max(len(p) for p in new.polylines), max(len(p) for p in prev.polylines), 2)))
    A = [_resample(p, m) for p in prev.polylines]
    B = [_resample(p, m) for p in new.polylines]
    k = len(B)
    ra, rb = _bounds(prev.polylines), _bounds(new.polylines)
    for i in range(k):
        fig.data[i].x, fig.data[i].y = A[i][:, 0], A[i][:, 1]
    fig.update_xaxes(range=[ra[0][0], ra[1][0]])
    fig.update_yaxes(range=[ra[0][1], ra[1][1]])
    frames = []
    for j in range(1, MORPH_STEPS + 1):
        last = j == MORPH_STEPS
        t = _smooth(j / MORPH_STEPS)
        data = []
        for i in range(k):
            if last:
                pl = new.polylines[i]
            else:
                pl = A[i] * (1 - t) + B[i] * t
            data.append(go.Scatter(x=pl[:, 0], y=pl[:, 1]))
        lo = ra[0] * (1 - t) + rb[0] * t
        hi = ra[1] * (1 - t) + rb[1] * t
        frames.append(go.Frame(data=data, traces=list(range(k)), name=str(j),
                               layout=dict(xaxis=dict(range=[lo[0], hi[0]]),
                                           yaxis=dict(range=[lo[1], hi[1]]))))
    fig.frames = frames
    return fig, True


def _morph_surface(fig, new, prev):
    if prev.Z.shape != new.Z.shape:
        return fig, False
    s = _stride(new.Z.shape)
    sub = lambda a: a[::s, ::s]
    pa = [sub(prev.X), sub(prev.Y), sub(prev.Z)]
    nb = [sub(new.X), sub(new.Y), sub(new.Z)]
    fig.data[0].x, fig.data[0].y, fig.data[0].z = pa
    frames = []
    for j in range(1, MORPH_STEPS + 1):
        if j == MORPH_STEPS:
            d = go.Surface(x=new.X, y=new.Y, z=new.Z)
        else:
            t = _smooth(j / MORPH_STEPS)
            x, y, z = (a * (1 - t) + b * t for a, b in zip(pa, nb))
            d = go.Surface(x=x, y=y, z=z)
        frames.append(go.Frame(data=[d], traces=[0], name=str(j)))
    fig.frames = frames
    return fig, True


def to_html(fig, animated=True):
    kw = dict(include_plotlyjs="cdn", full_html=False, config=dict(responsive=True))
    if animated:
        kw.update(auto_play=True, animation_opts=PLAY)
    return fig.to_html(**kw)


def sweep_figure(make_fig, spec, pvals, domain, n, name, lo, hi, steps=30):
    """Figure with a draggable slider + play button that sweeps parameter `name` over [lo, hi].
    Returns (fig, number_of_frames). Raises ValueError if nothing could be drawn."""
    vals = np.linspace(lo, hi, int(steps))
    results = []
    for v in vals:
        try:
            results.append((float(v), core.sample(spec, {**pvals, name: float(v)}, domain, int(n))))
        except Exception:
            continue
    if not results:
        raise ValueError("nothing to draw in this range")
    surface = results[0][1].kind == "surface"
    if surface:
        s = _stride(results[0][1].Z.shape)
        results = [(v, r) for v, r in results if r.Z.shape == results[0][1].Z.shape]
        fig = make_fig(results[0][1])
        fig.data[0].x, fig.data[0].y = results[0][1].X[::s, ::s], results[0][1].Y[::s, ::s]
        fig.data[0].z = results[0][1].Z[::s, ::s]
        frames = [go.Frame(data=[go.Surface(z=r.Z[::s, ::s])], traces=[0], name=str(i))
                  for i, (v, r) in enumerate(results)]
        zs = np.concatenate([r.Z[np.isfinite(r.Z)].ravel() for _, r in results] or [np.zeros(1)])
        if zs.size:
            fig.update_layout(scene=dict(zaxis=dict(range=[float(zs.min()), float(zs.max())])))
    else:
        results = [(v, r) for v, r in results if r.polylines]
        if not results:
            raise ValueError("nothing to draw in this range")
        k = max(len(r.polylines) for _, r in results)
        fig = make_fig(results[0][1])
        empty = np.empty((0, 2))
        for i in range(len(fig.data), k):
            fig.add_trace(go.Scatter(mode="lines", line=dict(color="#1f77b4"), showlegend=False))
        frames = []
        for i, (v, r) in enumerate(results):
            pls = list(r.polylines) + [empty] * (k - len(r.polylines))
            frames.append(go.Frame(data=[go.Scatter(x=p[:, 0], y=p[:, 1]) for p in pls],
                                   traces=list(range(k)), name=str(i)))
        lo_, hi_ = _bounds([np.vstack(r.polylines) for _, r in results])
        fig.update_xaxes(range=[lo_[0], hi_[0]])
        fig.update_yaxes(range=[lo_[1], hi_[1]])
    fig.frames = frames
    anim_args = lambda names: [names, dict(mode="immediate", frame=dict(duration=FRAME_MS, redraw=True),
                                           transition=dict(duration=0))]
    fig.update_layout(
        height=620,
        updatemenus=[dict(type="buttons", direction="left", x=0.0, y=0.0, xanchor="left", yanchor="top",
                          pad=dict(t=40),
                          buttons=[dict(label="Play", method="animate", args=[None, PLAY]),
                                   dict(label="Pause", method="animate",
                                        args=[[None], dict(mode="immediate", frame=dict(duration=0), transition=dict(duration=0))])])],
        sliders=[dict(x=0.15, len=0.85, pad=dict(t=40), currentvalue=dict(prefix=f"{name} = ", xanchor="left"),
                      steps=[dict(method="animate", args=anim_args([str(i)]), label=f"{v:.3g}")
                             for i, (v, _) in enumerate(results)])])
    return fig, len(frames)
