"""Raised surface textures for the form. Pure functions, no app dependencies.

A texture is a height field T(x, y) in [0, 1] (mm coordinates). The form builder multiplies it
by `height_mm` and adds it on top of the strand surface, so the pattern is raised and every
feature has soft, tapered sides (it presses and releases from the mould without undercuts).
"""
import numpy as np

KINDS = ["dots", "ridges", "crosshatch", "waves", "rings", "scales", "stipple"]


def _rot(X, Y, angle_deg):
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    return X * c + Y * s, -X * s + Y * c


def _bump(d, radius):
    """Smooth dome: 1 at d=0 falling to 0 at d=radius (cosine taper, zero slope at both ends)."""
    t = np.clip(1.0 - d / np.maximum(radius, 1e-9), 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * t)


def _hash(ix, iy, seed):
    """Deterministic pseudo-random value in [0, 1) per integer cell (vectorised)."""
    h = (np.asarray(ix, np.uint64) * np.uint64(374761393)
         + np.asarray(iy, np.uint64) * np.uint64(668265263)
         + np.uint64(int(seed) & 0xFFFF) * np.uint64(2147483647))
    m = np.uint64(0xFFFFFFFF)
    h &= m
    h = ((h ^ (h >> np.uint64(13))) * np.uint64(1274126177)) & m
    return ((h ^ (h >> np.uint64(16))) & np.uint64(0xFFFF)).astype(float) / 65536.0


def pattern(X, Y, kind="dots", pitch=0.8, feature=0.5, angle=0.0, seed=1):
    """Return the texture height field in [0, 1].

    pitch   centre-to-centre spacing in mm (> 0)
    feature 0.1..1.0, share of the pitch each raised feature covers (bigger = wider/denser)
    angle   rotation of the pattern in degrees
    seed    random seed (stipple only)
    """
    X = np.asarray(X, float)
    Y = np.asarray(Y, float)
    if kind not in KINDS:
        raise ValueError(f"unknown texture '{kind}'")
    pitch = float(pitch)
    if not np.isfinite(pitch) or pitch <= 0:
        raise ValueError("texture pitch must be above 0")
    feature = float(np.clip(feature, 0.1, 1.0))
    u, v = _rot(X, Y, angle)
    r = 0.5 * pitch * feature            # feature radius in mm

    if kind == "dots":                    # hexagonal dot grid
        row_h = pitch * np.sqrt(3) / 2
        j = np.round(v / row_h)
        off = 0.5 * pitch * (j % 2)
        i = np.round((u - off) / pitch)
        d1 = np.hypot(u - (i * pitch + off), v - j * row_h)
        out = _bump(d1, r)
        # neighbouring rows can also reach the point: take the max over +-1 rows
        for dj in (-1, 1):
            jj = j + dj
            offj = 0.5 * pitch * (jj % 2)
            ii = np.round((u - offj) / pitch)
            out = np.maximum(out, _bump(np.hypot(u - (ii * pitch + offj), v - jj * row_h), r))
        return out
    if kind == "ridges":                  # parallel rounded ridges
        d = np.abs(((u / pitch) + 0.5) % 1.0 - 0.5) * pitch
        return _bump(d, r)
    if kind == "crosshatch":              # two ridge sets at 90 degrees
        d1 = np.abs(((u / pitch) + 0.5) % 1.0 - 0.5) * pitch
        d2 = np.abs(((v / pitch) + 0.5) % 1.0 - 0.5) * pitch
        return np.maximum(_bump(d1, r), _bump(d2, r))
    if kind == "waves":                   # wavy ridges
        w = v + 0.35 * pitch * np.sin(2 * np.pi * u / (2.5 * pitch))
        d = np.abs(((w / pitch) + 0.5) % 1.0 - 0.5) * pitch
        return _bump(d, r)
    if kind == "rings":                   # concentric rings around the origin
        d = np.abs(((np.hypot(X, Y) / pitch) + 0.5) % 1.0 - 0.5) * pitch
        return _bump(d, r)
    if kind == "scales":                  # overlapping fish scales (arc ridges)
        row_h = pitch * 0.5
        j = np.floor(v / row_h)
        off = 0.5 * pitch * (j % 2)
        cx = (np.floor((u - off) / pitch) + 0.5) * pitch + off
        cy = (j + 1) * row_h
        d = np.abs(np.hypot(u - cx, v - cy) - 0.5 * pitch)
        arc = (v < cy).astype(float)      # keep the lower arc of each circle
        return _bump(d, r * 0.8) * arc
    # stipple: one randomly placed dot per cell
    ix = np.floor(u / pitch).astype(np.int64)  # may be negative; wraps harmlessly in uint64
    iy = np.floor(v / pitch).astype(np.int64)
    out = np.zeros_like(u)
    hv = _hash
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx_i, cy_i = ix + dx, iy + dy
            px = (cx_i + 0.15 + 0.7 * hv(cx_i, cy_i, seed)) * pitch
            py = (cy_i + 0.15 + 0.7 * hv(cx_i, cy_i, seed + 7)) * pitch
            size = r * (0.5 + 0.5 * hv(cx_i, cy_i, seed + 13))
            out = np.maximum(out, _bump(np.hypot(u - px, v - py), size))
    return out


def apply(H, px, mask_from=0.0, kind="dots", height_mm=0.15, pitch=0.8, feature=0.5,
          angle=0.0, seed=1, edge_mm=0.2, origin=(0.0, 0.0)):
    """Add the raised texture to heightmap H (mm, grid pitch px mm).

    Only pixels where H > mask_from are textured; the texture fades to zero within edge_mm of
    the strand edge so it never undercuts or runs over the wall. Returns a new array.
    """
    H = np.asarray(H, float)
    if height_mm <= 0:
        return H.copy()
    if not np.isfinite(height_mm) or height_mm > 2.0:
        raise ValueError("texture height must be between 0 and 2 mm")
    ny, nx = H.shape
    X = origin[0] + (np.arange(nx) * px)[None, :] * np.ones((ny, 1))
    Y = origin[1] + (np.arange(ny) * px)[:, None] * np.ones((1, nx))
    T = pattern(X, Y, kind, pitch, feature, angle, seed)
    inside = H > mask_from
    if not inside.any():
        return H.copy()
    # distance (mm) from the strand edge, so the pattern fades out smoothly near it
    from scipy import ndimage
    dist = ndimage.distance_transform_edt(inside) * px
    fade = np.clip(dist / max(edge_mm, px), 0.0, 1.0)
    fade = 0.5 - 0.5 * np.cos(np.pi * fade)
    return np.where(inside, H + height_mm * T * fade, H)
