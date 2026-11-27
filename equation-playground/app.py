"""Equation playground: type an equation, tweak parameters, build SVG / STL."""
import json

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import core
import dataclasses
import io
import pathlib
import types
import zipfile
import geometry as geo
import clay

EXAMPLES = {
    "explicit": "y = a sin(b x)",
    "implicit": "x^2 + y^2 = r^2",
    "parametric": "x = a cos(t) + cos(b t), y = a sin(t) - sin(b t)",
    "polar": "r = a + b cos(k theta)",
    "surface": "z = a sin(x) cos(y)",
}
EXAMPLE_ORDER = list(EXAMPLES)

st.set_page_config(page_title="Equation playground", layout="wide")
ss = st.session_state
ss.setdefault("text", EXAMPLES["polar"])
ss.setdefault("pstore", {})  # name -> dict(v, lo, hi, step)


# ---------- parameter state helpers ----------
def _store(name):
    return ss["pstore"].setdefault(name, dict(v=1.0, lo=-5.0, hi=5.0, step=0.01))


def _on_slider(name):
    _store(name)["v"] = ss[f"sl_{name}"]
    ss[f"nu_{name}"] = ss[f"sl_{name}"]


def _on_number(name):
    s = _store(name)
    v = min(max(ss[f"nu_{name}"], s["lo"]), s["hi"])
    s["v"] = v
    ss[f"sl_{name}"] = v
    ss[f"nu_{name}"] = v


def _on_range(name, field):
    s = _store(name)
    s[field] = ss[f"{field}_{name}"]
    if s["lo"] >= s["hi"]:
        s["hi"] = s["lo"] + 1.0
    s["v"] = min(max(s["v"], s["lo"]), s["hi"])


def _on_example():
    ss["text"] = EXAMPLES[ss["example"]]


def param_widgets(names):
    vals = {}
    for n in names:
        s = _store(n)
        s["v"] = min(max(s["v"], s["lo"]), s["hi"])
        # set widget state before instantiation (allowed), never after
        ss[f"sl_{n}"] = s["v"]
        ss[f"nu_{n}"] = s["v"]
        c1, c2 = st.columns([3, 1])
        c1.slider(n, s["lo"], s["hi"], step=s["step"], key=f"sl_{n}",
                  on_change=_on_slider, args=(n,))
        c2.number_input(n, step=s["step"], format="%.4g", key=f"nu_{n}",
                        label_visibility="collapsed", on_change=_on_number, args=(n,))
        with st.expander(f"{n}: min / max / step"):
            a, b, c = st.columns(3)
            ss[f"lo_{n}"], ss[f"hi_{n}"], ss[f"step_{n}"] = s["lo"], s["hi"], s["step"]
            a.number_input("min", key=f"lo_{n}", on_change=_on_range, args=(n, "lo"))
            b.number_input("max", key=f"hi_{n}", on_change=_on_range, args=(n, "hi"))
            c.number_input("step", min_value=1e-6, format="%.4g", key=f"step_{n}",
                           on_change=_on_range, args=(n, "step"))
        vals[n] = s["v"]
    return vals


# ---------- plotting ----------
def make_figure(res, equal):
    fig = go.Figure()
    if res.kind == "surface":
        fig.add_trace(go.Surface(x=res.X, y=res.Y, z=res.Z, colorscale="Viridis"))
        fig.update_layout(scene=dict(aspectmode="data"))
    else:
        for pl in res.polylines:
            fig.add_trace(go.Scatter(x=pl[:, 0], y=pl[:, 1], mode="lines",
                                     line=dict(color="#1f77b4"), showlegend=False))
        if equal:
            fig.update_yaxes(scaleanchor="x", scaleratio=1)
    fig.update_layout(height=520, margin=dict(l=10, r=10, t=10, b=10))
    return fig


def heightmap_figure(H, px, title):
    step = max(1, int(max(H.shape) // 160))
    Hs = H[::step, ::step]
    fig = go.Figure(go.Surface(z=Hs, x=np.arange(Hs.shape[1]) * px * step,
                               y=np.arange(Hs.shape[0]) * px * step, colorscale="Greys"))
    fig.update_layout(height=450, margin=dict(l=0, r=0, t=30, b=0), title=title,
                      scene=dict(aspectmode="data"))
    return fig


PRICES = pathlib.Path(__file__).with_name("prices.json")


def load_prices():
    try:
        return json.loads(PRICES.read_text())
    except Exception:
        return {}


def save_prices(d):
    try:
        if d != load_prices():
            PRICES.write_text(json.dumps(d, indent=1))
    except Exception:
        pass


def balls_figure(H, px, cb):
    step = max(1, int(max(H.shape) // 400))
    Hs = H[::step, ::step]
    fig = go.Figure(go.Heatmap(z=Hs, dx=px * step, dy=px * step, x0=0, y0=0,
                               colorscale=[[0, "#f4f1ec"], [1e-6, "#d9c7a8"], [1, "#8a6f45"]],
                               showscale=False, hoverinfo="skip"))
    r = cb["d_mm"] / 2
    for i, (x, y) in enumerate(cb["balls"], 1):
        fig.add_shape(type="circle", x0=x - r, x1=x + r, y0=y - r, y1=y + r,
                      line=dict(color="#c0392b", width=2), fillcolor="rgba(192,57,43,0.18)")
        fig.add_annotation(x=x, y=y, text=str(i), showarrow=False, font=dict(color="#c0392b", size=14))
    fig.update_yaxes(scaleanchor="x", scaleratio=1, title="mm")
    fig.update_xaxes(title="mm")
    fig.update_layout(height=520, margin=dict(l=10, r=10, t=10, b=10))
    return fig


def mesh_figure(mesh, title, target_faces=150000):
    v, f = np.asarray(mesh.vertices, float), np.asarray(mesh.faces, np.int64)
    if len(f) > target_faces:
        try:
            import fast_simplification as fs
            v, f = fs.simplify(v, f.astype(np.int32), target_reduction=1 - target_faces / len(f))
        except Exception:
            pass
    fig = go.Figure(go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], i=f[:, 0], j=f[:, 1], k=f[:, 2],
                              color="#c9b8a0", flatshading=False,
                              lighting=dict(ambient=0.45, diffuse=0.9, specular=0.25, roughness=0.6),
                              lightposition=dict(x=-200, y=300, z=400)))
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=30, b=0), title=title,
                      scene=dict(aspectmode="data", camera=dict(eye=dict(x=0.0, y=-1.3, z=1.9))))
    return fig


# ---------- sidebar: equation ----------
with st.sidebar:
    st.title("Equation playground")
    st.selectbox("Example", EXAMPLE_ORDER, key="example", on_change=_on_example,
                 format_func=lambda k: f"{k}: {EXAMPLES[k]}", index=3)
    st.text_area("Equation", key="text", height=90,
                 help="Parts separated by , ; or newline. Use ^ for power.")
    n_samples = st.number_input("Samples n", 50, 5000, 800, step=50)

spec, err = None, None
try:
    spec = core.parse(ss["text"])
    ss["last_spec"] = spec
except core.EquationError as e:
    err = str(e)
except Exception as e:  # defensive: never crash the UI on bad input
    err = f"could not parse: {e}"
if spec is None:
    spec = ss.get("last_spec")

if err:
    st.error(err + (" (showing last good plot)" if spec else ""))
if spec is None:
    st.info("Enter an equation in the sidebar.")
    st.stop()

with st.sidebar:
    st.caption(f"kind: {spec.kind}")
    st.latex(spec.latex)
    st.subheader("Parameters")
    if not spec.params:
        st.caption("No parameters detected.")
    pvals = param_widgets(spec.params)
    st.subheader("Ranges")
    domain = {}
    for ax, (d0, d1) in spec.domain.items():
        a, b = st.columns(2)
        k = f"dom_{spec.kind}_{ax}"
        lo = a.number_input(f"{ax} min", value=float(d0), key=k + "_lo", format="%.4g")
        hi = b.number_input(f"{ax} max", value=float(d1), key=k + "_hi", format="%.4g")
        domain[ax] = (lo, hi) if hi > lo else (d0, d1)
    equal = st.checkbox("Equal aspect", value=True)

# ---------- plot ----------
try:
    res = core.sample(spec, pvals, domain, int(n_samples))
    ss["last_res"] = res
except core.EquationError as e:
    st.error(str(e))
    res = ss.get("last_res")
except Exception as e:
    st.error(f"could not sample: {e}")
    res = ss.get("last_res")

if res is None:
    st.stop()
for w in res.warnings:
    st.warning(w)
st.plotly_chart(make_figure(res, equal), width="stretch")

# ---------- make it ----------
st.header("Make it")
c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("Form")
    size = st.number_input("Size (mm)", 5.0, 200.0, 40.0, step=1.0)
    sw = st.number_input("Strand width (mm)", 0.4, 10.0, 1.8, step=0.1)
    sh = st.number_input("Strand height (mm)", 0.3, 10.0, 1.2, step=0.1)
    draft = st.number_input("Draft (deg)", 0.0, 45.0, 20.0, step=1.0)
    px = st.number_input("Pixel (mm)", 0.02, 0.2, 0.05, step=0.01, format="%.3f")
with c2:
    st.subheader("Form extras")
    loop = st.checkbox("Hanging loop", value=True)
    loop_auto = st.checkbox("Loop auto (top, over centre of mass)", value=True, disabled=not loop)
    loop_angle = st.slider("Loop position (deg, 0 right, 90 top)", 0.0, 360.0, 90.0, step=1.0,
                           disabled=(not loop) or loop_auto)
    loop_shift = st.number_input("Loop shift out (+) / in (-) (mm)", -5.0, 10.0, 0.0, step=0.1, disabled=not loop)
    loop_od = st.number_input("Loop outer dia (mm)", 2.0, 20.0, 5.0, step=0.1, disabled=not loop)
    loop_id = st.number_input("Loop hole dia (mm)", 0.8, 15.0, 1.8, step=0.1, disabled=not loop)
    loop_h = st.number_input("Loop height (mm)", 0.5, 10.0, 1.5, step=0.1, disabled=not loop)
    rot = st.slider("Rotate shape (deg)", -180.0, 180.0, 0.0, step=1.0, help="2D kinds. Turns the shape before the loop is placed.")
    flip = st.checkbox("Mirror shape left-right", value=False)
    relief = st.number_input("Relief (mm, surface)", 0.5, 20.0, 3.0, step=0.5)
    base = st.number_input("Base plate (mm)", 0.0, 5.0, 0.0, step=0.2)
with c3:
    st.subheader("Mould")
    pair = st.checkbox("Pair (L + mirrored R)", value=True)
    wall = st.number_input("Floor wall (mm)", 1.0, 15.0, 3.0, step=0.5)
    margin = st.number_input("Margin (mm)", 1.0, 20.0, 6.5, step=0.5, help="Pins need 6.3 or more.")
    lid_t = st.number_input("Lid thickness (mm)", 1.0, 15.0, 5.0, step=0.5)
    overflow = st.checkbox("Overflow gutter + vent lines", value=True)
    vents = st.number_input("Vent lines per cavity", 0, 12, 4, step=1)
    pockets = st.checkbox("Relief pockets in enclosed gaps", value=True)
    two_sided = st.radio("Form type", ["Full 3D (two halves)", "Flat back (mould + lid)"],
                         help="Full 3D: bottom + top half pressed together, piece domed both sides. "
                              "Flat back: one mould, flat lid.").startswith("Full")
    pins = st.checkbox("Alignment pins", value=two_sided, key=f"pins_{two_sided}",
                       help="3 pins on the lid / top half, sockets in the mould. One pin oversize.")

form_opt = geo.FormOptions(size_mm=size, strand_w=sw, strand_h=sh, draft_deg=draft, px=px,
                           loop=loop, relief_mm=relief, base_mm=base,
                           loop_auto=loop_auto, loop_angle_deg=loop_angle, loop_shift_mm=loop_shift,
                           loop_od=loop_od, loop_id=loop_id, loop_h=loop_h)
mould_opt = geo.MouldOptions(wall=wall, margin=margin, pair=pair, lid_t=lid_t, overflow=overflow,
                             vents=int(vents), pockets=pockets, two_sided=two_sided, pins=pins)
key = json.dumps([ss["text"], pvals, domain, int(n_samples), vars(form_opt), vars(mould_opt), rot, flip],
                 sort_keys=True, default=str)

def placed(res):
    """Result with rotate / mirror applied (2D kinds only)."""
    if res.kind == "surface" or (rot == 0 and not flip):
        return res
    c, s_ = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    R = np.array([[c, -s_], [s_, c]])
    pl = [(p * ([-1, 1] if flip else [1, 1])) @ R.T for p in res.polylines]
    return types.SimpleNamespace(kind=res.kind, polylines=pl, closed=res.closed, X=None, Y=None, Z=None)


bc = st.columns([1, 1, 3])
do_draft = bc[0].button("Draft build", help="Fast look: 0.1 mm pixel. Not for printing.")
do_final = bc[1].button("Build", type="primary", help="Print quality at the Pixel size set above.")
if do_draft or do_final:
    with st.spinner("Building (draft about 5 s, final 10-25 s)..."):
        try:
            bpx = max(px, 0.1) if do_draft else px
            fo = dataclasses.replace(form_opt, px=bpx)
            out = geo.build_all(placed(res), fo, mould_opt)
            ss["build"] = dict(
                key=key, svg=out.get("svg"), check=out["check"], H=out["H"], px=bpx, draft=do_draft,
                form_stl=geo.stl_bytes(out["form"]), mould_stl=geo.stl_bytes(out["mould"]),
                lid_stl=geo.stl_bytes(out["lid"]), form=out["form"], mould=out["mould"], lid=out["lid"],
                two_sided=bool(out.get("two_sided")), pair=bool(pair),
                design=dict(equation=ss["text"], params=pvals, domain=domain, rotate_deg=rot, mirror=flip,
                            form=vars(fo), mould=vars(mould_opt)),
            )
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"build failed: {e}")

b = ss.get("build")
if b:
    if b["key"] != key:
        st.info("Inputs changed since this build. Press Build to refresh.")
    if b.get("draft"):
        st.warning("Draft build (0.1 mm pixel). Press Build before printing.")
    chk = b["check"]
    st.subheader("Check")
    mf, mg = chk.get("min_feature_mm"), chk.get("min_gap_mm")
    dims = lambda k: " x ".join(f"{v:.1f}" for v in chk.get(k, [])) + " mm"
    st.table({
        "Form (w, h, t)": dims("form_mm"),
        "Mould block": dims("block_mm"),
        "Resin for mould": f"{chk.get('resin_ml', 0):.1f} ml",
        "Clay per piece": f"{chk.get('clay_cm3', 0):.2f} cm3",
        "Separate pieces": str(chk.get("bodies", "?")),
        "Enclosed gaps / relief pockets": f"{chk.get('enclosed_gaps', 'n/a')} / {chk.get('pockets', 'n/a')}",
        "Hang tilt": "n/a" if chk.get("hang_tilt_deg") is None else f"{chk['hang_tilt_deg']:.1f} deg",
        "Vent lines / pins": f"{chk.get('vents', 'n/a')} / {chk.get('pins', 'n/a')}",
        "Max thickness": f"{chk.get('max_thick_mm', 0):.2f} mm",
        "Thinnest feature": "n/a" if mf is None else f"{mf:.2f} mm",
        "Thinnest resin wall": "n/a" if mg is None else f"{mg:.2f} mm",
        "Watertight form / mould": f"{chk.get('form_watertight')} / {chk.get('mould_watertight')}",
    })
    for w in chk.get("warnings", []):
        st.warning(w)
    if not chk.get("warnings"):
        st.success("No warnings.")

    # ---------- clay (editor only, never in the STL) ----------
    st.subheader("Clay")
    k1, k2, k3 = st.columns(3)
    extra = k1.number_input("Extra clay (%)", 0.0, 100.0, 15.0, step=1.0,
                            help="Over the exact cavity volume. Goes to overflow lines.")
    nballs = k2.number_input("Balls per piece (0 = auto)", 0, 12, 0, step=1)
    show_balls = k3.checkbox("Show ball placement", value=True)
    try:
        cb = clay.clay_balls(b["H"], b["px"], two_sided=b.get("two_sided", False),
                             extra_pct=extra, n=int(nballs))
        st.markdown(f"**{cb['n']} balls of {cb['d_mm']:.1f} mm** per piece. "
                    f"Cavity {cb['cavity_mm3'] / 1000:.3f} cm3, clay {cb['clay_mm3'] / 1000:.3f} cm3, "
                    f"about {cb['grams']:.2f} g. Placement shows in this editor only, not in any STL.")
        if cb["share_err_pct"] > 15:
            st.caption(f"Ball zones uneven by up to {cb['share_err_pct']:.0f}%. Push clay toward thin areas.")
        if show_balls:
            st.plotly_chart(balls_figure(b["H"], b["px"], cb), width="stretch")
    except ValueError as e:
        cb = None
        st.warning(str(e))

    # ---------- cost ----------
    st.subheader("Cost")
    saved = load_prices()
    q = st.columns(4)
    clay_paid = q[0].number_input("Clay: price paid", 0.0, 10000.0, float(saved.get("clay_paid", 0.0)), step=0.5)
    clay_g = q[1].number_input("Clay: amount bought (g)", 1.0, 100000.0, float(saved.get("clay_g", 1000.0)), step=10.0)
    resin_paid = q[2].number_input("Resin: price paid", 0.0, 10000.0, float(saved.get("resin_paid", 0.0)), step=0.5)
    resin_ml_b = q[3].number_input("Resin: amount bought (ml)", 1.0, 100000.0, float(saved.get("resin_ml", 1000.0)), step=50.0)
    q = st.columns(4)
    waste = q[0].number_input("Clay waste (%)", 0.0, 100.0, float(saved.get("waste", 0.0)), step=1.0,
                              help="Clay lost per press on top of the ball amount.")
    uses = q[1].number_input("Presses per mould", 1, 100000, int(saved.get("uses", 50)), step=10,
                             help="How many presses the printed mould is expected to last.")
    save_prices(dict(clay_paid=clay_paid, clay_g=clay_g, resin_paid=resin_paid, resin_ml=resin_ml_b,
                     waste=waste, uses=uses))
    if cb:
        per_press = 2 if b.get("pair") else 1
        clay_cost = cb["grams"] * (1 + waste / 100) * clay_paid / clay_g
        resin_ml = (b["mould"].volume + b["lid"].volume) / 1000.0
        mould_cost = resin_ml * resin_paid / resin_ml_b
        mould_share = mould_cost / uses / per_press
        st.table({
            "Clay price": f"{clay_paid / clay_g:.4f} per g",
            "Clay per piece": f"{cb['grams'] * (1 + waste / 100):.2f} g = {clay_cost:.3f}",
            "Mould set resin": f"{resin_ml:.1f} ml = {mould_cost:.2f}",
            "Mould share per piece": f"{mould_share:.4f} (over {uses} presses, {per_press} per press)",
            "Material cost per piece": f"{clay_cost + mould_share:.3f}",
            "Material cost per pair": f"{2 * (clay_cost + mould_share):.3f}",
        })
        st.caption("Clay grams use density 1.7 g/cm3 (approximate). Weigh one ball to correct. "
                   "Excludes findings, glaze, power, time.")

    part2 = "Top half" if b.get("two_sided") else "Lid"
    view = st.radio("3D preview", ["Mould", part2, "Form", "Heightmap"], horizontal=True)
    if view == "Mould":
        st.plotly_chart(mesh_figure(b["mould"], "Mould"), width="stretch")
    elif view == part2:
        st.plotly_chart(mesh_figure(b["lid"], part2), width="stretch")
    elif view == "Form":
        st.plotly_chart(mesh_figure(b["form"], "Form"), width="stretch")
    else:
        st.plotly_chart(heightmap_figure(b["H"], b["px"], "Heightmap"), width="stretch")

    d = st.columns(4)
    if b["svg"]:
        d[0].download_button("SVG", b["svg"].encode("utf-8"), "curve.svg", "image/svg+xml")
    d[1].download_button("Form STL", b["form_stl"], "form.stl", "model/stl")
    d[2].download_button("Mould STL", b["mould_stl"], "mould.stl", "model/stl")
    d[3].download_button(f"{part2} STL", b["lid_stl"], "top_half.stl" if b.get("two_sided") else "lid.stl", "model/stl")

    def make_zip():
        buf = io.BytesIO()
        info = dict(design=b["design"], check=chk)
        if cb:
            info["clay"] = dict(balls_per_piece=cb["n"], ball_d_mm=round(cb["d_mm"], 2),
                                cavity_cm3=round(cb["cavity_mm3"] / 1000, 4), clay_cm3=round(cb["clay_mm3"] / 1000, 4),
                                grams=round(cb["grams"], 3), ball_xy_mm=[[round(v, 2) for v in p] for p in cb["balls"]])
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            if b["svg"]:
                z.writestr("curve.svg", b["svg"])
            z.writestr("form.stl", b["form_stl"])
            z.writestr("mould.stl", b["mould_stl"])
            z.writestr("top_half.stl" if b.get("two_sided") else "lid.stl", b["lid_stl"])
            z.writestr("design.json", json.dumps(info, indent=1, default=str))
        return buf.getvalue()

    if st.checkbox("Prepare zip of everything (STLs, SVG, design.json with equation, settings, clay balls)"):
        st.download_button("Download zip", make_zip(), "equation_mould.zip", "application/zip")
