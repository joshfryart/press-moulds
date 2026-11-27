import numpy as np
import clay


def ring(px=0.05):
    yy, xx = np.mgrid[0:800, 0:800] * px
    r = np.hypot(xx - 20, yy - 20)
    return np.where(np.abs(r - 15) < 0.9, 1.2 * np.sqrt(np.clip(1 - ((r - 15) / 0.9) ** 2, 0, 1)), 0)


def test_volume_matches_analytic_ring():
    c = clay.clay_balls(ring(), 0.05, two_sided=False, extra_pct=0)
    exact = 2 * np.pi * 15 * (np.pi / 2 * 0.9 * 1.2)        # torus-like: path length x half-ellipse area
    assert abs(c["cavity_mm3"] - exact) / exact < 0.01
    assert abs(c["clay_mm3"] - c["cavity_mm3"]) < 1e-9


def test_two_sided_doubles_and_balls_sum_to_clay():
    H = ring()
    a = clay.clay_balls(H, 0.05, two_sided=False)
    b = clay.clay_balls(H, 0.05, two_sided=True)
    assert abs(b["cavity_mm3"] - 2 * a["cavity_mm3"]) < 1e-6
    assert abs(b["n"] * np.pi / 6 * b["d_mm"] ** 3 - b["clay_mm3"]) < 1e-6
    assert b["d_mm"] <= 7.0


def test_balls_sit_on_cavity_and_count_is_respected():
    H = ring()
    c = clay.clay_balls(H, 0.05, n=4)
    assert c["n"] == 4 and len(c["balls"]) == 4
    for x, y in c["balls"]:
        assert H[int(round(y / 0.05)), int(round(x / 0.05))] > 0
    assert c["share_err_pct"] < 10
