"""Curves / surface -> SVG, positive form STL, open-face press mould STL, lid / top half, printability check.

Method follows spiral_v2.py / earring v6: strands are rasterised to a heightmap (domed ridge,
flat back, drafted walls, so no undercuts by construction), the mould block is a grid solid with
the heightmap cut into its top face plus flash gutter, vents and relief pockets, bottom edge chamfered.
All lengths in mm. Heightmap H[i, j] sits at (x0 + j*px, y0 + i*px), rows run with +y (y up).
"""
from dataclasses import dataclass
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree
import trimesh
import fast_simplification

VENT_W = 1.2                                  # vent width (spiral_v2 vent_w)
MIN_GAP, MIN_FEATURE = 0.6, 1.0               # warning thresholds
FORM_FACES, MOULD_FACES = 400_000, 600_000
PIN_WALL = 1.0                                # resin around a pin socket, each side
PIN_TIP_DEG = 30.0                            # pin tip chamfer, from the pin axis
H_EPS = 1e-6                                  # mm; heights below this are rounding noise, treated as 0


@dataclass
class FormOptions:
    size_mm: float = 40.0
    strand_w: float = 1.8
    strand_h: float = 1.2
    draft_deg: float = 20.0
    px: float = 0.05
    loop: bool = True
    relief_mm: float = 3.0
    base_mm: float = 0.0
    loop_od: float = 5.0
    loop_id: float = 1.8
    loop_h: float = 1.5
    loop_auto: bool = True          # top of form, over centre of mass x
    loop_angle_deg: float = 90.0    # loop_auto False: direction from centre of mass, 0 right, 90 top, CCW
    loop_shift_mm: float = 0.0      # + outward (bridged by a strand), - sunk into the form


@dataclass
class MouldOptions:
    wall: float = 3.0
    margin: float = 4.0
    pad: float = 4.0
    land: float = 0.8
    gutter_w: float = 1.6
    gutter_d: float = 0.8
    chamfer: float = 0.5
    pair: bool = True
    gap: float = 1.0
    lid_t: float = 5.0
    overflow: bool = True           # gutter ring + vent channels
    vents: int = 4                  # vent channels per cavity
    pockets: bool = True            # relief pockets in enclosed gaps (spiral_v2 shunt)
    pocket_land: float = 0.6
    pocket_w: float = 0.6
    pocket_min: float = 0.3
    two_sided: bool = False         # piece domed both sides; second part = mirrored top half
    pins: bool = False              # alignment pins on the second part, sockets in the bottom mould
    pin_d: float = 3.0
    pin_h: float = 2.0
    pin_clear: float = 0.15


class HeightMap(np.ndarray):
    """ndarray carrying .info (loop position etc.). Derived arrays do not inherit it."""
    def __new__(cls, a, info=None):
        obj = np.asarray(a, float).view(cls); obj.info = dict(info or {}); return obj

    def __array_finalize__(self, obj):
        self.info = {}


def _pos(name, v):
    """v must be a finite number > 0 (a zero would give an empty / non-watertight / divide-by-zero build)."""
    try:
        ok = np.isfinite(v) and v > 0
    except TypeError:
        ok = False
    if not ok:
        raise ValueError("%s must be a number > 0 (got %r)" % (name, v))


def _check_form_opt(opt):
    for n in ("size_mm", "px", "strand_w", "strand_h"):
        _pos(n, getattr(opt, n))
    if opt.loop:
        _pos("loop_h", opt.loop_h)


def _check_mould_opt(opt):
    _pos("wall", opt.wall)
    _pos("chamfer", opt.chamfer)             # 0 leaves a degenerate bottom edge (not watertight)
    if opt.pins:
        _pos("pin_d", opt.pin_d)


def _check_H(H, px):
    _pos("px", px)
    if not np.isfinite(np.asarray(H, float)).all():
        raise ValueError("heightmap contains NaN or inf")


# ---------------------------------------------------------------- 2D

def fit_polylines(polylines, size_mm):
    """Uniform scale so the largest bbox side is size_mm, bbox centred at origin, y up."""
    pts = [np.asarray(p, float) for p in polylines if p is not None and len(p) >= 2]
    if not pts:
        return []
    allp = np.vstack(pts)
    lo, hi = allp.min(0), allp.max(0)
    span = float((hi - lo).max())
    s = size_mm / span if span > 1e-12 else 1.0
    c = (lo + hi) / 2
    return [(p - c) * s for p in pts]


def to_svg(polylines_mm, stroke_mm=1.8):
    pts = [np.asarray(p, float) for p in polylines_mm if len(p) >= 2]
    if not pts:
        lo, hi = np.zeros(2), np.ones(2)
    else:
        allp = np.vstack(pts); lo, hi = allp.min(0), allp.max(0)
    m = stroke_mm
    x0, y0 = lo[0] - m, -hi[1] - m           # y flipped: svg y = -y
    w, h = hi[0] - lo[0] + 2 * m, hi[1] - lo[1] + 2 * m
    paths = []
    for p in pts:
        d = "M" + " L".join("%.3f %.3f" % (x, -y) for x, y in p)
        if np.allclose(p[0], p[-1], atol=1e-6):
            d += " Z"
        paths.append('<path d="%s"/>' % d)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%.3fmm" height="%.3fmm" '
            'viewBox="%.3f %.3f %.3f %.3f">\n'
            '<g fill="none" stroke="black" stroke-width="%.3f" stroke-linecap="round" '
            'stroke-linejoin="round">\n%s\n</g>\n</svg>\n'
            % (w, h, x0, y0, w, h, stroke_mm, "\n".join(paths)))


# ---------------------------------------------------------------- heightmaps

def _profile(d, r, h, tanw):
    """spiral_v2 strand profile: dome capped by the draft line, 0 outside."""
    q = np.clip(d / r, 0, 1)
    z = np.where(d < r, np.minimum(h * np.sqrt(1 - q * q), (r - d) * tanw), 0.0)
    return np.where(z > H_EPS, z, 0.0)


def _resample(p, step, closed):
    p = np.asarray(p, float)
    if closed and not np.allclose(p[0], p[-1]):
        p = np.vstack([p, p[:1]])
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    if s[-1] <= 0:
        return p[:1]
    n = int(np.ceil(s[-1] / step)) + 1
    u = np.linspace(0, s[-1], n)
    return np.c_[np.interp(u, s, p[:, 0]), np.interp(u, s, p[:, 1])]


def _crop(H, origin, px, pad_mm):
    """Crop H to the bbox of H>0 plus pad_mm of zeros; returns (H, origin)."""
    H = np.asarray(H)
    ys, xs = np.nonzero(H > 0)
    if len(ys) == 0:
        raise ValueError("nothing to build")
    k = int(np.ceil(pad_mm / px))
    i0, i1, j0, j1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    Hc = np.pad(H[i0:i1, j0:j1], k)
    return Hc, (origin[0] + (j0 - k) * px, origin[1] + (i0 - k) * px)


def _window(shape, x0, y0, px, lo, hi):
    """Pixel window covering the mm box lo..hi; returns (slices, X, Y)."""
    ny, nx = shape
    j0 = max(0, int((lo[0] - x0) / px) - 2); j1 = min(nx, int((hi[0] - x0) / px) + 3)
    i0 = max(0, int((lo[1] - y0) / px) - 2); i1 = min(ny, int((hi[1] - y0) / px) + 3)
    X, Y = np.meshgrid(x0 + np.arange(j0, j1) * px, y0 + np.arange(i0, i1) * px)
    return (slice(i0, i1), slice(j0, j1)), X, Y


def _com(H, x0, y0, px):
    w = H.sum()
    return np.array([x0 + (H.sum(0) * np.arange(H.shape[1])).sum() / w * px,
                     y0 + (H.sum(1) * np.arange(H.shape[0])).sum() / w * px])


def _hole_tangent(P, base, u, rh):
    """Hole (radius rh) centre on the line base + t*u, just outside every form point P near the line.
    Returns (centre, contact point) or None."""
    n = np.array([-u[1], u[0]])
    rel = P - base; s = rel @ u; lat = rel @ n
    band = (np.abs(lat) < rh) & (s > 0)      # only form beyond the base point: the loop goes on the far side
    if not band.any():                       # nothing there: slide the line to the far end of the form
        far = s > 0 if (s > 0).any() else np.ones(len(s), bool)
        cand = np.nonzero(far & (s >= s[far].max() - rh))[0]
        k = cand[np.argmin(np.abs(lat[cand]))]
        base = base + lat[k] * n; rel = P - base; s = rel @ u; lat = rel @ n
        band = (np.abs(lat) < rh) & (s > 0)
        if not band.any():
            band = np.abs(lat) < rh
    t = s[band] + np.sqrt(np.maximum(rh * rh - lat[band] ** 2, 0))
    k = np.argmax(t)
    return base + u * t[k], P[np.nonzero(band)[0][k]]


def _add_loop(Hs, x0, y0, px, opt, tanw):
    """Ring (spiral_v2 ring profile) attached outside the form; hole edge touches the form edge."""
    od, idd, rh = opt.loop_od, opt.loop_id, opt.loop_id / 2
    rc = (od + idd) / 4; rw = (od - idd) / 4; rs = opt.strand_w / 2
    ii, jj = np.nonzero(Hs > 0)
    P = np.c_[x0 + jj * px, y0 + ii * px]
    com = _com(Hs, x0, y0, px)
    if opt.loop_auto:
        u = np.array([0.0, 1.0]); xc = com[0]; iters = 4
    else:
        a = np.radians(opt.loop_angle_deg); u = np.array([np.cos(a), np.sin(a)]); iters = 1
    H = Hs; ctr = None
    for _ in range(iters):
        base = np.array([xc, com[1]]) if opt.loop_auto else com
        c0, contact = _hole_tangent(P, base, u, rh)
        ctr = c0 + u * (px / 2 + opt.loop_shift_mm)
        H = Hs.copy()
        sl, X, Y = _window(H.shape, x0, y0, px, ctr - od / 2, ctr + od / 2)
        H[sl] = np.maximum(H[sl], _profile(np.abs(np.hypot(X - ctr[0], Y - ctr[1]) - rc), rw, opt.loop_h, tanw))
        if opt.loop_shift_mm > 0:            # bridge strand from the form to the ring
            end = ctr - u * (rh + rs)
            if (end - contact) @ u > 0:
                sl, X, Y = _window(H.shape, x0, y0, px, np.minimum(contact, end) - rs, np.maximum(contact, end) + rs)
                v = end - contact; L2 = v @ v
                tt = np.clip(((X - contact[0]) * v[0] + (Y - contact[1]) * v[1]) / L2, 0, 1)
                d = np.hypot(X - contact[0] - tt * v[0], Y - contact[1] - tt * v[1])
                H[sl] = np.maximum(H[sl], _profile(d, rs, opt.strand_h, tanw))
        sl, X, Y = _window(H.shape, x0, y0, px, ctr - rh, ctr + rh)
        H[sl][np.hypot(X - ctr[0], Y - ctr[1]) < rh] = 0.0     # hole always open
        if opt.loop_auto:
            xn = _com(H, x0, y0, px)[0]       # loop over centre of mass so it hangs straight
            if abs(xn - xc) < px:
                break
            xc = xn
    return H, ctr


def curve_heightmap(polylines_mm, closed, opt: FormOptions):
    _check_form_opt(opt)
    px = opt.px; r = opt.strand_w / 2; tanw = np.tan(np.radians(90 - opt.draft_deg))
    if opt.loop and not (0 < opt.loop_id < opt.loop_od - 0.8):
        raise ValueError("loop hole must be smaller than loop outer dia - 0.8 mm")
    closed = list(closed) + [False] * (len(polylines_mm) - len(closed))
    lines = [_resample(p, px / 2, c) for p, c in zip(polylines_mm, closed) if len(p) >= 2]
    if not lines:
        raise ValueError("no curve to build")
    allp = np.vstack(lines)
    pad = r + 2 * px
    if opt.loop:
        pad += opt.loop_od + max(opt.loop_shift_mm, 0) + 0.5
    lo = allp.min(0) - pad; hi = allp.max(0) + pad
    xs = np.arange(lo[0], hi[0] + px, px); ys = np.arange(lo[1], hi[1] + px, px)
    nx, ny = len(xs), len(ys)
    # only query pixels near the centreline: rasterise points and dilate
    near = np.zeros((ny, nx), bool)
    ij = np.round((allp - lo) / px).astype(int)
    near[ij[:, 1], ij[:, 0]] = True
    near = ndimage.distance_transform_edt(~near) * px <= r + 2 * px
    ii, jj = np.nonzero(near)
    Q = np.c_[lo[0] + jj * px, lo[1] + ii * px]
    d, _ = cKDTree(allp).query(Q, distance_upper_bound=r + px, workers=-1)
    H = np.zeros((ny, nx))
    H[ii, jj] = _profile(np.where(np.isfinite(d), d, r + 1), r, opt.strand_h, tanw)
    x0, y0 = float(lo[0]), float(lo[1])
    ctr = None
    if opt.loop and H.max() > 0:
        H, ctr = _add_loop(H, x0, y0, px, opt, tanw)
    Hc, org = _crop(H, (x0, y0), px, 0.5)
    info = {}
    if ctr is not None:
        info = dict(loop_ctr_px=((ctr[1] - org[1]) / px, (ctr[0] - org[0]) / px),
                    loop_od=opt.loop_od, loop_id=opt.loop_id)
    return HeightMap(Hc, info), org


def surface_heightmap(X, Y, Z, opt: FormOptions):
    _check_form_opt(opt)
    px = opt.px; tanw = np.tan(np.radians(90 - opt.draft_deg))
    X = np.asarray(X, float); Y = np.asarray(Y, float); Z = np.asarray(Z, float)
    xa, ya = X[0, :], Y[:, 0]
    if xa[-1] < xa[0]: X, Y, Z = X[:, ::-1], Y[:, ::-1], Z[:, ::-1]; xa = X[0, :]
    if ya[-1] < ya[0]: X, Y, Z = X[::-1], Y[::-1], Z[::-1]; ya = Y[:, 0]
    fin = np.isfinite(Z)
    if not fin.any():
        raise ValueError("surface is empty (all values undefined)")
    fy, fx = np.nonzero(fin)
    bx0, bx1, by0, by1 = xa[fx.min()], xa[fx.max()], ya[fy.min()], ya[fy.max()]
    span = max(bx1 - bx0, by1 - by0)
    s = opt.size_mm / span if span > 0 else 1.0
    w, h = (bx1 - bx0) * s, (by1 - by0) * s
    u = np.arange(0, w + px / 2, px); v = np.arange(0, h + px / 2, px)
    dx = (xa[-1] - xa[0]) / max(len(xa) - 1, 1); dy = (ya[-1] - ya[0]) / max(len(ya) - 1, 1)
    fj = (bx0 + u / s - xa[0]) / (dx if dx else 1); fi = (by0 + v / s - ya[0]) / (dy if dy else 1)
    FI, FJ = np.meshgrid(fi, fj, indexing="ij")
    idx = ndimage.distance_transform_edt(~fin, return_distances=False, return_indices=True)
    Zf = Z[tuple(idx)]                                  # nan filled with nearest value for interpolation
    zi = ndimage.map_coordinates(Zf, [FI, FJ], order=1, mode="nearest")
    mask = ndimage.map_coordinates(fin.astype(float), [FI, FJ], order=1, mode="nearest") >= 0.5
    zmin, zmax = Z[fin].min(), Z[fin].max()
    t = (zi - zmin) / (zmax - zmin) if zmax > zmin else np.ones_like(zi)
    hmin = min(0.6, opt.relief_mm)
    H = np.where(mask, hmin + np.clip(t, 0, 1) * (opt.relief_mm - hmin), 0.0)
    Hp = np.pad(H, 1)                                   # draft the footprint edge (no vertical wall)
    e = ndimage.distance_transform_edt(Hp > 0)[1:-1, 1:-1] * px
    H = np.minimum(H, e * tanw)
    Hc, org = _crop(H, (-w / 2, -h / 2), px, 0.5)
    return HeightMap(Hc), org


# ---------------------------------------------------------------- meshes

def _grid_solid(Z, px, ch, z0=0.0):
    """spiral_v2 grid_solid: heightmap top, vertical sides, bottom chamfer, flat fan bottom."""
    ny, nx = Z.shape
    xs = np.arange(nx) * px; ys = np.arange(ny) * px
    X, Y = np.meshgrid(xs, ys)
    top = np.c_[X.ravel(), Y.ravel(), Z.ravel()]; N = nx * ny
    id_ = np.arange(N).reshape(ny, nx)
    a, b, c, d = id_[:-1, :-1].ravel(), id_[:-1, 1:].ravel(), id_[1:, 1:].ravel(), id_[1:, :-1].ravel()
    F = [np.c_[a, b, c], np.c_[a, c, d]]
    border = [id_[0, :], id_[:, -1], id_[-1, ::-1], id_[::-1, 0]]
    rt = np.concatenate([e[:-1] for e in border]); K = len(rt)
    mid = top[rt].copy(); mid[:, 2] = z0 + ch
    low = top[rt].copy(); low[:, 2] = z0
    low[:, 0] = ch + low[:, 0] * (xs[-1] - 2 * ch) / xs[-1]; low[:, 1] = ch + low[:, 1] * (ys[-1] - 2 * ch) / ys[-1]
    V = np.vstack([top, mid, low, [[xs[-1] / 2, ys[-1] / 2, z0]]])
    im = N + np.arange(K); il = N + K + np.arange(K); ic = N + 2 * K
    nx_ = lambda v: np.roll(v, -1)
    F += [np.c_[nx_(rt), rt, im], np.c_[nx_(rt), im, nx_(im)]]
    F += [np.c_[nx_(im), im, il], np.c_[nx_(im), il, nx_(il)]]
    F.append(np.c_[nx_(il), il, np.full(K, ic)])
    return V, np.vstack(F)


def _dedup(F):
    key = np.sort(F, axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    return F[cnt[inv.ravel()] == 1]


def _finish(V, F, target):
    """spiral_v2 save(): simplify, drop duplicated faces (both copies), fix orientation.
    Falls back to milder simplification if the result is not a clean closed solid."""
    T = V[F]
    vol0 = float(np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6)
    tries = [target, int(target * 1.5), len(F)] if len(F) > target else [len(F)]
    tm = None
    for t in tries:
        if t < len(F):
            V2, F2 = fast_simplification.simplify(V.astype(np.float32), F.astype(np.int32),
                                                  target_reduction=1 - t / len(F))
        else:
            V2, F2 = V, F
        tm = trimesh.Trimesh(V2.astype(float), _dedup(F2), process=True)
        if tm.volume < 0:
            tm.invert()
        if tm.is_watertight and tm.volume > 0 and abs(tm.volume - abs(vol0)) < 0.01 * abs(vol0) + 1e-6:
            return tm
    return tm


def form_mesh(H, px, base_mm=0.0, two_sided=False):
    """Positive form. Flat back at z=0, or with two_sided a solid mirrored about z=0 (base_mm ignored)."""
    _check_H(H, px)
    H = np.pad(np.asarray(H, float), 1)
    H = np.where(H > H_EPS, H, 0.0)
    if base_mm > 0 and not two_sided:        # flat plate under the form: one grid solid
        V, F = _grid_solid(H + base_mm, px, min(0.3, base_mm / 2))
        return _finish(V, F, FORM_FACES)
    # Top surface = heightmap; bottom = same grid at z=0 (or -H). Zero-height vertices are shared by
    # top and bottom (edge where the drafted wall meets the back), all-zero triangles dropped.
    ny, nx = H.shape; N = nx * ny
    X, Y = np.meshgrid(np.arange(nx) * px, np.arange(ny) * px)
    hz = H.ravel()
    id_ = np.arange(N).reshape(ny, nx)
    a, b, c, d = id_[:-1, :-1].ravel(), id_[:-1, 1:].ravel(), id_[1:, 1:].ravel(), id_[1:, :-1].ravel()
    T = np.vstack([np.c_[a, b, c], np.c_[a, c, d]])
    lift = np.zeros(N, bool)
    for _ in range(6):
        pos = (hz > 0) | lift
        keep = pos[T].any(1); Tk = T[keep]
        used = np.unique(Tk)
        sep = used[pos[used]]                # vertices that get their own bottom copy
        bot = np.arange(N); bot[sep] = N + np.arange(len(sep))
        Fb = bot[Tk][:, ::-1]
        F = np.vstack([Tk, Fb])
        e = np.sort(np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
        sh = np.zeros(N + len(sep), bool); sh[:N] = ~pos
        e = e[sh[e[:, 0]] & sh[e[:, 1]]]     # only edges between two shared vertices can pinch
        ue, cnt = np.unique(e[:, 0].astype(np.int64) * (2 * N) + e[:, 1], return_counts=True)
        ue = np.c_[ue // (2 * N), ue % (2 * N)]
        bad = ue[cnt > 2]
        if len(bad) == 0:
            break
        lift[bad[bad < N]] = True            # pinched zero edge: give it a hair of thickness
    z = np.where(lift & (hz <= 0), 1e-3, hz)
    zb = -z[sep] if two_sided else np.zeros(len(sep))
    V = np.vstack([np.c_[X.ravel(), Y.ravel(), z], np.c_[X.ravel()[sep], Y.ravel()[sep], zb]])
    return _finish(V, F, FORM_FACES)


def _disk(r_px):
    k = int(np.ceil(r_px)); yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    return xx * xx + yy * yy <= r_px * r_px


def _cavity_relief(H, opt: MouldOptions, px, hole_rc):
    """spiral_v2 shunt(): flash gutter + vents (bottom only) and relief pockets (both halves).
    The loop hole is never pocketed (solid post). Returns Rb, Rt, vents, stats."""
    gd = opt.gutter_d
    M = H > 0
    dist = ndimage.distance_transform_edt(~M) * px
    lab, n = ndimage.label(~M)
    outside = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]).tolist()) - {0}
    out = np.isin(lab, list(outside))
    hole = -1
    if hole_rc is not None:
        r, c = hole_rc
        if 0 <= r < H.shape[0] and 0 <= c < H.shape[1] and not M[r, c]:
            hole = int(lab[r, c])
    enclosed = [i for i in range(1, n + 1) if i not in outside and i != hole]
    Rb = np.zeros_like(H); npk = 0
    if opt.pockets and enclosed:
        dk = _disk(max(1.0, opt.pocket_w / 2 / px))
        objs = ndimage.find_objects(lab)
        for i in enclosed:
            sl = objs[i - 1]
            pk = (lab[sl] == i) & (dist[sl] > opt.pocket_land)
            pk = ndimage.binary_dilation(ndimage.binary_erosion(pk, dk), dk) & pk
            if pk.sum() * px * px < opt.pocket_min:
                continue
            Rb[sl][pk] = gd; npk += 1
    Rt = Rb.copy()
    vents = []
    if opt.overflow:
        Rb[out & (dist > opt.land) & (dist <= opt.land + opt.gutter_w)] = gd
        vents = _place_vents(M, out, dist, opt, px)
        hw = max(1, int(round(VENT_W / px / 2))); ny, nx = H.shape
        for dr, i, j in vents:
            if dr == "+x": Rb[i - hw:i + hw + 1, j:] = gd
            if dr == "-x": Rb[i - hw:i + hw + 1, :j + 1] = gd
            if dr == "+y": Rb[i:, j - hw:j + hw + 1] = gd
            if dr == "-y": Rb[:i + 1, j - hw:j + hw + 1] = gd
    return Rb, Rt, vents, dict(enclosed_gaps=len(enclosed), pockets=npk)


def _place_vents(M, out, dist, opt, px):
    """Straight vents from the gutter ring to the box edge, clear of the form, spread around it."""
    n = int(opt.vents)
    if n <= 0:
        return []
    hw = max(1, int(round(VENT_W / px / 2))); ny, nx = M.shape
    free = (out & (dist > opt.land)).astype(np.uint8)
    ring = out & (np.abs(dist - (opt.land + opt.gutter_w / 2)) <= 0.75 * px)
    Fx = ndimage.minimum_filter1d(free, 2 * hw + 1, axis=0, mode="constant", cval=0).astype(bool)
    Fy = ndimage.minimum_filter1d(free, 2 * hw + 1, axis=1, mode="constant", cval=0).astype(bool)
    clear = {"+x": np.logical_and.accumulate(Fx[:, ::-1], axis=1)[:, ::-1],
             "-x": np.logical_and.accumulate(Fx, axis=1),
             "+y": np.logical_and.accumulate(Fy[::-1], axis=0)[::-1],
             "-y": np.logical_and.accumulate(Fy, axis=0)}
    dvec = {"+x": (0, 1), "-x": (0, -1), "+y": (1, 0), "-y": (-1, 0)}
    fi, fj = np.nonzero(M); ci, cj = fi.mean(), fj.mean()
    rform = 0.5 * max(np.ptp(fi), np.ptp(fj)) + 1
    cand = []
    for dr, ok in clear.items():
        ii, jj = np.nonzero(ring & ok)
        di, dj = dvec[dr]
        sel = di * (ii - ci) + dj * (jj - cj) > 0
        ii, jj = ii[sel], jj[sel]
        ln = {"+x": nx - 1 - jj, "-x": jj, "+y": ny - 1 - ii, "-y": ii}[dr]
        cand += [(dr, ii, jj, ln)]
    chosen = []
    for k in range(n):
        a = 2 * np.pi * k / n
        best = None
        for dr, ii, jj, ln in cand:
            if len(ii) == 0:
                continue
            diff = np.abs((np.arctan2(ii - ci, jj - cj) - a + np.pi) % (2 * np.pi) - np.pi)
            ok = diff <= np.pi / n + 1e-9
            for dr2, i2, j2 in chosen:       # keep vents apart
                if dr2 == dr:
                    off = np.abs(ii - i2) if dr[1] == "x" else np.abs(jj - j2)
                    ok &= off > 2 * hw + int(1.0 / px)
                ok &= np.hypot(ii - i2, jj - j2) * px > 3.0
            if not ok.any():
                continue
            cost = ln + rform * diff
            cost = np.where(ok, cost, np.inf); m = int(np.argmin(cost))
            if best is None or cost[m] < best[0]:
                best = (cost[m], dr, int(ii[m]), int(jj[m]))
        if best is not None:
            chosen.append(best[1:])
    return chosen


def _pin_z(dist, d, pin_h, px):
    """Pin heightmap: cylinder with a chamfered tip (PIN_TIP_DEG off axis). Grid walls slope over one
    pixel: pin vertices stop 0.5 px inside d/2, socket vertices 0.5 px outside, so mid-wall clearance = pin_clear."""
    rp = d / 2; c = min(0.4, rp / 2)
    z = pin_h - np.maximum(0, dist - (rp - c)) / np.tan(np.radians(PIN_TIP_DEG))
    return np.where(dist <= rp - 0.5 * px, z, 0.0)


def mould_mesh(H, opt: MouldOptions, px):
    info_in = getattr(H, "info", {}) or {}
    _check_mould_opt(opt); _check_H(H, px)
    H, org = _crop(np.asarray(H, float), (0.0, 0.0), px, opt.pad)
    hole_rc = None
    if "loop_ctr_px" in info_in:
        r, c = info_in["loop_ctr_px"]
        hole_rc = (int(round(r - org[1] / px)), int(round(c - org[0] / px)))
    Rb, Rt, vents, st = _cavity_relief(H, opt, px, hole_rc)
    T = float(H.max()) + opt.wall
    warnings = []
    margin = opt.margin
    if opt.pins:
        need = opt.pin_d + 1.0 + 2 * opt.pin_clear + 2 * PIN_WALL
        if margin < need:
            margin = need; warnings.append("margin grown to %.1f mm for pins" % need)
    m = int(round(margin / px)); g = int(round(opt.gap / px)); ny, nx = H.shape
    ncav = 2 if opt.pair else 1
    BY, BX = ny + 2 * m, ncav * nx + (ncav - 1) * g + 2 * m
    Db = np.zeros((BY, BX)); Dt = np.zeros((BY, BX))
    Db[m:m + ny, m:m + nx] = H + Rb; Dt[m:m + ny, m:m + nx] = H + Rt
    cr = m + nx + g
    if opt.pair:
        Db[m:m + ny, cr:cr + nx] = (H + Rb)[:, ::-1]; Dt[m:m + ny, cr:cr + nx] = (H + Rt)[:, ::-1]
    Zb = T - Db
    hw = max(1, int(round(VENT_W / px / 2))); vz = T - opt.gutter_d
    strips = []                              # vent continuation through margin / gap, block coords
    for dr, i, j in vents:
        boxes = [(m, dr, j)] + ([(cr, {"+x": "-x", "-x": "+x"}.get(dr, dr), nx - 1 - j)] if opt.pair else [])
        for c0, d2, jj in boxes:
            if d2 == "+x": strips.append((slice(m + i - hw, m + i + hw + 1), slice(c0 + nx, BX if c0 == cr or not opt.pair else cr)))
            if d2 == "-x": strips.append((slice(m + i - hw, m + i + hw + 1), slice(0 if c0 == m else m + nx, c0)))
            if d2 == "+y": strips.append((slice(m + ny, BY), slice(c0 + jj - hw, c0 + jj + hw + 1)))
            if d2 == "-y": strips.append((slice(0, m), slice(c0 + jj - hw, c0 + jj + hw + 1)))
    if opt.pair and any(dr == "+x" for dr, _, _ in vents):
        gc = m + nx + g // 2
        strips.append((slice(0, BY), slice(gc - hw, gc + hw + 1)))   # shared channel between cavities
    for s in strips:
        Zb[s] = np.minimum(Zb[s], vz)
    sockets, pins2 = [], []
    if opt.pins:
        h = (m - 1) / 2
        for (r, c), d in [((h, h), opt.pin_d), ((BY - 1 - h, BX - 1 - h), opt.pin_d), ((BY - 1 - h, h), opt.pin_d + 1.0)]:
            x, y = c * px, r * px
            sockets.append((x, y, d)); pins2.append(((BX - 1) * px - x, y, d))
            rs = d / 2 + opt.pin_clear
            sl, X, Y = _window(Zb.shape, 0, 0, px, (x - rs - 1, y - rs - 1), (x + rs + 1, y + rs + 1))
            sk = np.hypot(X - x, Y - y) <= rs + 0.5 * px
            Zb[sl][sk] = np.minimum(Zb[sl][sk], T - (opt.pin_h + 0.3))
        if T - (opt.pin_h + 0.3) < 1.0:
            warnings.append("socket floor %.1f mm < 1.0 mm" % (T - opt.pin_h - 0.3))
    V, F = _grid_solid(Zb, px, opt.chamfer)
    mesh = _finish(V, F, MOULD_FACES)
    mesh.metadata["mould_info"] = dict(
        st, vents=len(vents), pins=3 if opt.pins else 0, two_sided=bool(opt.two_sided), warnings=warnings,
        T=T, px=px, chamfer=opt.chamfer, shape=(BY, BX), margin=margin, sockets=sockets, pins_xy=pins2,
        pin_h=opt.pin_h, top_Z=(T - Dt[:, ::-1]) if opt.two_sided else None)
    return mesh


def lid_mesh(mould, opt: MouldOptions):
    """Second part: plain plate, plate with pins, or (two_sided) the mirrored top half with pins."""
    info = getattr(mould, "metadata", {}).get("mould_info")
    lo, hi = mould.bounds
    if info is None or (not info["two_sided"] and not info["pins"]):
        w, h = hi[0] - lo[0], hi[1] - lo[1]
        lid = trimesh.creation.box(extents=[w, h, opt.lid_t])
        lid.apply_translation([lo[0] + w / 2, lo[1] + h / 2, opt.lid_t / 2])
        return lid
    px = info["px"]; BY, BX = info["shape"]; W, Hh = (BX - 1) * px, (BY - 1) * px
    if info["two_sided"]:
        Z = info["top_Z"].copy(); face = info["T"]; s = np.ones(2)
    else:                                    # flat plate: a coarser grid is enough (speed)
        px = max(px, 0.1)
        nx2, ny2 = int(round(W / px)) + 1, int(round(Hh / px)) + 1
        s = np.array([W / ((nx2 - 1) * px), Hh / ((ny2 - 1) * px)])    # stretch to the exact footprint
        Z = np.full((ny2, nx2), float(opt.lid_t)); face = float(opt.lid_t)
    for x, y, d in info["pins_xy"]:
        x, y = x / s[0], y / s[1]
        sl, X, Y = _window(Z.shape, 0, 0, px, (x - d, y - d), (x + d, y + d))
        Z[sl] = np.maximum(Z[sl], face + _pin_z(np.hypot(X - x, Y - y), d, info["pin_h"], px))
    V, F = _grid_solid(Z, px, info["chamfer"])
    V[:, :2] *= s
    return _finish(V, F, MOULD_FACES)


def stl_bytes(mesh):
    return mesh.export(file_type="stl")


# ---------------------------------------------------------------- check

def _thinnest(mask, px, r_max_mm, frac=0.6):
    """Opening test: smallest disk radius whose opening removes a whole feature (not just corner
    slivers). Returns width in mm or None if nothing is removed up to r_max_mm."""
    D = ndimage.distance_transform_edt(mask)
    def removes(r):
        E = D > r
        O = ndimage.distance_transform_edt(~E) <= r
        lost = mask & ~O
        if not lost.any():
            return False
        lab, n = ndimage.label(lost, structure=np.ones((3, 3)))
        mx = ndimage.maximum(ndimage.distance_transform_edt(lost), lab, np.arange(1, n + 1))
        cnt = ndimage.sum(lost, lab, np.arange(1, n + 1))
        big = mx >= max(frac * r, 1.5)
        thin = (mx >= min(1.5, r)) & (cnt >= 6 * r)     # 1-2 px wide strip (0.1-0.2 mm): long, not a corner sliver
        return bool(np.any(big | thin))
    # ascending scan (a whole thin feature is only recognised near r = w/2), then bisect
    lo, hi, r = 0.5, None, 1.0
    while r <= r_max_mm / px:
        if removes(r):
            hi = r; break
        lo = r; r = max(r * 1.35, r + 0.5)
    if hi is None:
        return None
    while hi - lo > 0.1:
        mid = (lo + hi) / 2
        if removes(mid): hi = mid
        else: lo = mid
    # a strip n px wide has EDT peak ceil(n/2) px, and vanishes at r = peak: n = 2r - 1 (odd) or 2r (even)
    return round((2 * hi - 0.5) * px, 2)


def check(H, px, form, mould, two_sided=None):
    hinfo = getattr(H, "info", {}) or {}
    minfo = (getattr(mould, "metadata", None) or {}).get("mould_info", {}) if mould is not None else {}
    if two_sided is None:
        two_sided = bool(minfo.get("two_sided", False))
    k2 = 2 if two_sided else 1
    _check_H(H, px)
    H = np.asarray(H, float); M = H > 0
    warnings = []
    _, bodies = ndimage.label(M)
    ys, xs = np.nonzero(M)
    form_mm = [round(float((xs.max() - xs.min() + 1) * px), 1), round(float((ys.max() - ys.min() + 1) * px), 1),
               round(float(H.max()) * k2, 2)] if len(xs) else [0.0, 0.0, 0.0]
    # opening tests at the true pixel size (subsampling made 0.5-0.6 mm gaps read 0.7+)
    k3 = int(np.ceil(3.0 / px)) + 2
    Mp = np.pad(M, k3)
    feat = _thinnest(Mp, px, 3.0) if len(xs) else None
    gap = _thinnest(~Mp, px, 1.5)
    if feat is None and len(xs):
        feat = 6.0                            # nothing removed by opening radii up to 3 mm: every part is >= 6 mm wide
    tilt = None
    if "loop_ctr_px" in hinfo and len(xs):
        r, c = hinfo["loop_ctr_px"]; com = _com(H, 0, 0, 1)
        tilt = round(float(np.degrees(np.arctan2(com[0] - c, r - com[1]))), 1)
    info = dict(
        bodies=int(bodies), form_mm=form_mm,
        clay_cm3=round(float(H.sum()) * px * px / 1000 * k2, 3),
        max_thick_mm=round(float(H.max()) * k2, 2),
        min_feature_mm=feat, min_gap_mm=gap,
        form_watertight=None if form is None else bool(form.is_watertight),
        mould_watertight=None if mould is None else bool(mould.is_watertight),
        block_mm=None, resin_ml=None,
        enclosed_gaps=minfo.get("enclosed_gaps"), pockets=minfo.get("pockets"),
        vents=minfo.get("vents"), pins=minfo.get("pins", 0), two_sided=bool(two_sided),
        hang_tilt_deg=tilt)
    if mould is not None:
        info["block_mm"] = [round(float(v), 1) for v in mould.extents]
        info["resin_ml"] = round(float(mould.volume) / 1000, 1)
    if bodies == 0:
        warnings.append("form is empty")
    elif bodies > 1:
        warnings.append("form is %d separate pieces" % bodies)
    if gap is not None and gap < MIN_GAP:
        warnings.append("resin wall %.2f mm < %.1f mm" % (gap, MIN_GAP))
    if feat is not None and feat < MIN_FEATURE:
        warnings.append("feature %.2f mm < %.1f mm" % (feat, MIN_FEATURE))
    if "loop_od" in hinfo:
        rw = (hinfo["loop_od"] - hinfo["loop_id"]) / 2
        if rw < 0.8:
            warnings.append("loop ring wall %.2f mm < 0.8 mm" % rw)
        if hinfo["loop_id"] < 1.2:
            warnings.append("loop hole %.2f mm < 1.2 mm" % hinfo["loop_id"])
    if tilt is not None and abs(tilt) > 5:
        warnings.append("hangs tilted %.0f deg" % tilt)
    warnings += list(minfo.get("warnings", []))
    if form is not None and not form.is_watertight:
        warnings.append("form STL is not watertight")
    if mould is not None:
        if not mould.is_watertight:
            warnings.append("mould STL is not watertight")
        elif len(mould.split(only_watertight=False)) > 1:
            warnings.append("mould STL has more than one body")
    info["warnings"] = warnings
    return info


# ---------------------------------------------------------------- all in one

def build_all(result, form_opt, mould_opt):
    _check_form_opt(form_opt); _check_mould_opt(mould_opt)
    px = form_opt.px
    two = bool(getattr(mould_opt, "two_sided", False))
    if result.kind == "surface":
        if result.Z is None or not np.isfinite(np.asarray(result.Z, float)).any():
            raise ValueError("nothing to build: surface is empty")
        H, _ = surface_heightmap(result.X, result.Y, result.Z, form_opt)
        svg = None
    else:
        polys = list(result.polylines or []); cl = list(result.closed or [])
        cl += [False] * (len(polys) - len(cl))
        pairs = [(p, c) for p, c in zip(polys, cl) if p is not None and len(p) >= 2]
        if not pairs:
            raise ValueError("nothing to build: no curve")
        closed = [c for _, c in pairs]
        pm = fit_polylines([p for p, _ in pairs], form_opt.size_mm)
        svg = to_svg(pm, form_opt.strand_w)
        H, _ = curve_heightmap(pm, closed, form_opt)
    form = form_mesh(H, px, form_opt.base_mm, two_sided=two)
    mould = mould_mesh(H, mould_opt, px)
    lid = lid_mesh(mould, mould_opt)
    return {"svg": svg, "form": form, "mould": mould, "lid": lid,
            "check": check(H, px, form, mould, two_sided=two), "H": H, "two_sided": two}
