import numpy as np
import pytest

import texture


def grid(n=120, step=0.05):
    x = np.arange(n) * step
    return np.meshgrid(x, x)


@pytest.mark.parametrize("kind", texture.KINDS)
def test_pattern_range_and_shape(kind):
    X, Y = grid()
    T = texture.pattern(X, Y, kind, pitch=1.0, feature=0.6, angle=15)
    assert T.shape == X.shape
    assert np.isfinite(T).all() and T.min() >= 0 and T.max() <= 1.0 + 1e-9
    assert T.max() > 0.9 and T.mean() < 0.8     # has features, not flat


def test_bad_inputs():
    X, Y = grid(10)
    with pytest.raises(ValueError):
        texture.pattern(X, Y, "nope")
    with pytest.raises(ValueError):
        texture.pattern(X, Y, "dots", pitch=0)


def test_stipple_seed_changes_pattern_but_is_repeatable():
    X, Y = grid()
    a = texture.pattern(X, Y, "stipple", 0.8, 0.6, seed=1)
    b = texture.pattern(X, Y, "stipple", 0.8, 0.6, seed=1)
    c = texture.pattern(X, Y, "stipple", 0.8, 0.6, seed=2)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_apply_raises_only_inside_and_fades_at_edge():
    H = np.zeros((100, 100)); H[:, 30:70] = 1.2
    H2 = texture.apply(H, 0.05, mask_from=0.01, kind="ridges", height_mm=0.2, pitch=0.6, feature=0.8)
    assert np.array_equal(H2[:, :30], H[:, :30]) and np.array_equal(H2[:, 70:], H[:, 70:])
    assert H2.max() <= 1.4 + 1e-9 and H2.max() > 1.3
    assert np.allclose(H2[:, 30], 1.2)          # edge pixel untouched (fade is 0 at the edge)
    assert (H2 >= H - 1e-12).all()


def test_apply_zero_height_and_limits():
    H = np.ones((20, 20))
    assert np.array_equal(texture.apply(H, 0.05, height_mm=0), H)
    with pytest.raises(ValueError):
        texture.apply(H, 0.05, height_mm=5)
