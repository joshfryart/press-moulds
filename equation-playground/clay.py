"""Clay amount as caliper-measured balls, and where to put each ball in the cavity.
Editor aid only: nothing here goes into any STL."""
import numpy as np

DENSITY_G_CM3 = 1.7     # polymer clay, approximate


def ball_diameter(volume_mm3):
    return float((6.0 * volume_mm3 / np.pi) ** (1.0 / 3.0))


def clay_balls(H, px, two_sided=False, extra_pct=15.0, n=0, max_d=7.0, seed=0):
    """H: form heightmap (mm), px: pixel size (mm).
    Returns dict: cavity_mm3 (exact form volume of ONE piece), clay_mm3 (with extra),
    grams, n, d_mm (every ball same diameter), balls [(x_mm, y_mm)] in heightmap coords
    (x = column * px, y = row * px), share_err_pct (worst ball-zone volume error)."""
    H = np.asarray(H, float)
    cavity = float(H.sum()) * px * px * (2.0 if two_sided else 1.0)
    if cavity <= 0:
        raise ValueError("empty form")
    clay = cavity * (1.0 + extra_pct / 100.0)
    ys, xs = np.nonzero(H > 0)
    w = H[ys, xs]
    P = np.c_[xs, ys] * px
    if len(P) > 6000:                                   # thin out, keep weights
        idx = np.random.default_rng(seed).choice(len(P), 6000, replace=False)
        P, w = P[idx], w[idx]
    w = w / w.sum()
    if n <= 0:                                          # auto: balls <= max_d, and one per ~15 mm of form
        ext = float(max(np.ptp(P[:, 0]), np.ptp(P[:, 1])))
        n = max(1, int(np.ceil(ext / 15.0)))
        while ball_diameter(clay / n) > max_d and n < 12:
            n += 1
    n = int(min(n, len(P)))
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
    return dict(cavity_mm3=cavity, clay_mm3=clay, grams=clay / 1000.0 * DENSITY_G_CM3, n=n,
                d_mm=ball_diameter(clay / n), balls=balls,
                share_err_pct=float(np.abs(share * n - 1.0).max() * 100.0))
