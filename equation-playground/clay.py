"""Clay amount as caliper-measured balls, and where to put each ball in the cavity.
Editor aid only: nothing here goes into any STL."""
import numpy as np

MAX_AUTO_BALLS = 12
DENSITY_G_CM3 = 1.35    # polymer clay, approximate (default)
CLAY_TYPES = {          # approximate densities, g/cm3; weigh a ball to correct
    "Polymer clay (about 1.35 g/cm3)": 1.35,
    "Low-fire earthenware (about 1.7 g/cm3)": 1.7,
}


def ball_diameter(volume_mm3):
    return float((6.0 * max(float(volume_mm3), 0.0) / np.pi) ** (1.0 / 3.0))


def clay_balls(H, px, two_sided=False, extra_pct=15.0, n=0, max_d=7.0, seed=0,
               base_mm=0.0, density=None):
    """H: form heightmap (mm), px: pixel size (mm).
    Returns dict: cavity_mm3 (exact form volume of ONE piece), clay_mm3 (with extra),
    grams, n, d_mm (every ball same diameter), balls [(x_mm, y_mm)] in heightmap coords
    (x = column * px, y = row * px), share_err_pct (worst ball-zone volume error),
    warning (str or None: balls bigger than max_d). base_mm (one-sided only) adds a flat plate
    under the whole grid: base_mm3 is returned and counted in cavity/clay. density in g/cm3."""
    H = np.asarray(H, float)
    if not (np.isfinite(px) and px > 0):
        raise ValueError("pixel size must be positive")
    if not np.isfinite(extra_pct) or extra_pct <= -100:
        raise ValueError("extra clay must be above -100%")
    if not np.isfinite(max_d) or max_d <= 0:
        raise ValueError("max ball diameter must be positive")
    if H.size == 0 or not np.isfinite(H).all():
        raise ValueError("empty form")
    cavity = float(H.sum()) * px * px * (2.0 if two_sided else 1.0)
    if cavity <= 0:
        raise ValueError("empty form")
    base_mm3 = 0.0
    if base_mm and base_mm > 0 and not two_sided:
        base_mm3 = float(H.shape[0] * H.shape[1]) * px * px * float(base_mm)
        cavity += base_mm3
    clay = cavity * (1.0 + extra_pct / 100.0)
    ys, xs = np.nonzero(H > 0)
    w = H[ys, xs]
    P = np.c_[xs, ys] * px
    if len(P) > 6000:                                   # thin out, keep weights
        idx = np.random.default_rng(seed).choice(len(P), 6000, replace=False)
        P, w = P[idx], w[idx]
    w = w / w.sum()
    n_auto = n <= 0
    if n_auto:                                          # auto: balls <= max_d, and one per ~15 mm of form
        ext = float(max(np.ptp(P[:, 0]), np.ptp(P[:, 1])))
        n = min(MAX_AUTO_BALLS, max(1, int(np.ceil(ext / 15.0))))
        while ball_diameter(clay / n) > max_d and n < MAX_AUTO_BALLS:
            n += 1
    n = int(min(n, len(P)))
    d_mm = ball_diameter(clay / n)
    warning = None
    if d_mm > max_d:
        warning = (f"Balls are {d_mm:.1f} mm, over the {max_d:g} mm target"
                   + (f" (auto mode stops at {MAX_AUTO_BALLS} balls)" if n_auto else "")
                   + ". Set more balls by hand or use less clay.")
    # equal-volume zones: k-means with a per-zone bias (power diagram), so every ball is the same size
    rng = np.random.default_rng(seed)
    C = P[rng.choice(len(P), n, replace=False, p=w)]
    bias = np.zeros(n)
    scale = float(np.ptp(P, axis=0).max()) ** 2 / max(n, 1)
    for it in range(80):
        d2 = ((P[:, None, :] - C[None, :, :]) ** 2).sum(-1) + bias
        lab = d2.argmin(1)
        share = np.bincount(lab, weights=w, minlength=n)
        for k in range(n):
            if share[k] > 0:
                C[k] = (P[lab == k] * w[lab == k, None]).sum(0) / share[k]
            else:
                C[k] = P[rng.integers(len(P))]
        bias += 0.5 * scale * (share - 1.0 / n)
        bias -= bias.mean()
    # put each ball on the nearest real cavity point to its zone centre
    balls = []
    for k in range(n):
        Q = P[lab == k] if (lab == k).any() else P
        balls.append(tuple(float(v) for v in Q[((Q - C[k]) ** 2).sum(1).argmin()]))
    balls.sort(key=lambda b: (-b[1], b[0]))            # top to bottom, left to right
    return dict(cavity_mm3=cavity, clay_mm3=clay, grams=clay / 1000.0 * (DENSITY_G_CM3 if density is None else float(density)), n=n,
                base_mm3=base_mm3,
                d_mm=d_mm, warning=warning, balls=balls,
                share_err_pct=float(np.abs(share * n - 1.0).max() * 100.0))
