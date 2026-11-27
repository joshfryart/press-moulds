"""Math core of the equation playground: parse any equation, detect its kind and
slider parameters, and sample it to polylines or a surface grid. No UI, no mesh."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import sympy as sp
from sympy.core.function import AppliedUndef
from sympy.parsing.sympy_parser import (
    convert_xor,
    function_exponentiation,
    implicit_application,
    implicit_multiplication,
    parse_expr,
    standard_transformations,
)


class EquationError(ValueError):
    """Short message, shown to the user verbatim."""


AXIS_NAMES = {"x", "y", "z", "t", "theta", "r"}
KINDS = ("explicit", "implicit", "parametric", "polar", "surface")
MAX_LEN = 500
TWO_PI = 2 * np.pi

_X, _Y, _Z, _T, _TH, _R = sp.symbols("x y z t theta r")
_AX = {"x": _X, "y": _Y, "z": _Z, "t": _T, "theta": _TH, "r": _R}

_FUNCS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot, "sec": sp.sec, "csc": sp.csc,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan, "atan2": sp.atan2,
    "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "asinh": sp.asinh, "acosh": sp.acosh, "atanh": sp.atanh,
    "arcsinh": sp.asinh, "arccosh": sp.acosh, "arctanh": sp.atanh,
    "exp": sp.exp, "log": sp.log, "ln": sp.log, "sqrt": sp.sqrt, "cbrt": sp.cbrt,
    "abs": sp.Abs, "Abs": sp.Abs, "floor": sp.floor, "ceil": sp.ceiling, "ceiling": sp.ceiling,
    "sign": sp.sign, "sgn": sp.sign, "Heaviside": sp.Heaviside, "heaviside": sp.Heaviside,
    "min": sp.Min, "max": sp.Max, "Min": sp.Min, "Max": sp.Max, "Mod": sp.Mod, "mod": sp.Mod,
}
_CONSTS = {"pi": sp.pi, "e": sp.E, "E": sp.E}
_GLOBALS = {
    "__builtins__": {},
    "Integer": sp.Integer, "Float": sp.Float, "Rational": sp.Rational,
    "Symbol": sp.Symbol, "Function": sp.Function,
}
_TRANSFORMS = standard_transformations + (
    convert_xor, implicit_multiplication, implicit_application, function_exponentiation,
)
_UNICODE = {
    "π": "pi", "θ": "theta", "φ": "phi", "ϕ": "phi", "α": "alpha", "β": "beta",
    "ω": "omega", "λ": "lam", "μ": "mu", "σ": "sigma", "τ": "tau",
    "²": "^2", "³": "^3", "×": "*", "·": "*", "⋅": "*", "−": "-", "–": "-", "÷": "/",
}


@dataclass
class Spec:
    text: str
    kind: str
    params: list[str]
    defaults: dict[str, float]
    domain: dict[str, tuple[float, float]]
    latex: str
    _axes: list[str] = field(default_factory=list, repr=False)
    _exprs: list = field(default_factory=list, repr=False)       # sympy exprs (one per output coord)
    _funcs: list = field(default_factory=list, repr=False)       # compiled numpy lambdas


@dataclass
class Result:
    kind: str
    polylines: list[np.ndarray]
    closed: list[bool]
    X: np.ndarray | None
    Y: np.ndarray | None
    Z: np.ndarray | None
    warnings: list[str]


# ---------------------------------------------------------------- parsing

def _check_safe(text: str) -> None:
    if len(text) > MAX_LEN:
        raise EquationError(f"equation too long (max {MAX_LEN} characters)")
    low = text.lower()
    if "__" in text or "import" in low or "lambda" in low:
        raise EquationError("not allowed in an equation")
    if re.search(r"\.\s*[A-Za-z_]", text):
        raise EquationError("not allowed in an equation: attribute access")
    if re.search(r"[<>≤≥≠]|!=", text):
        raise EquationError("not supported: inequalities")
    if "'" in text or '"' in text or re.search(r"\bd\s*/\s*d[a-z]", text):
        raise EquationError("not supported: derivatives / ODEs")
    if re.search(r"[\[\]{}@`$\\#]", text):
        raise EquationError("could not parse: unexpected symbol")


def _normalise(text: str) -> str:
    for k, v in _UNICODE.items():
        text = text.replace(k, v)
    # |u| -> abs(u) (non-nested bars only)
    text = re.sub(r"\|([^|]+)\|", r"abs(\1)", text)
    if "|" in text:
        raise EquationError("could not parse: unmatched |")
    # 2x -> 2*x, 2theta -> 2*theta (not 1e5, not k1x)
    text = re.sub(r"\b(\d+(?:\.\d*)?)(?![eE][+-]?\d)(?=[A-Za-z_])", r"\1*", text)
    return text


def _split_parts(text: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if depth == 0 and ch in ",;\n":
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _parse_expr(s: str) -> sp.Expr:
    if not s.strip():
        raise EquationError("missing expression on one side of '='")
    local = dict(_FUNCS)
    local.update(_CONSTS)
    local.update(_AX)
    try:
        e = parse_expr(s, local_dict=local, global_dict=dict(_GLOBALS),
                       transformations=_TRANSFORMS, evaluate=True)
    except EquationError:
        raise
    except Exception:
        raise EquationError(f"could not parse: {s.strip()[:40]}")
    if isinstance(e, bool) or e in (sp.true, sp.false):
        raise EquationError(f"could not parse: {s.strip()[:40]}")
    if isinstance(e, (tuple, list)):
        raise EquationError("could not parse: unexpected comma")
    if not isinstance(e, sp.Expr):
        raise EquationError(f"could not parse: {s.strip()[:40]}")
    undef = e.atoms(AppliedUndef)
    if undef:
        name = sorted(str(f.func) for f in undef)[0]
        raise EquationError(f"not supported: unknown function {name}()")
    if e.has(sp.I):
        raise EquationError("not supported: complex numbers")
    if e.has(sp.zoo, sp.oo, -sp.oo, sp.nan):
        raise EquationError("expression is undefined (division by zero?)")
    return e


def _parse_part(p: str):
    sides = p.split("=")
    if len(sides) == 1:
        return None, _parse_expr(sides[0])
    if len(sides) == 2:
        return _parse_expr(sides[0]), _parse_expr(sides[1])
    raise EquationError("could not parse: use a single '=' per equation")


def _names(e) -> set[str]:
    return {s.name for s in e.free_symbols}


def parse(text: str) -> Spec:
    if text is None or not str(text).strip():
        raise EquationError("enter an equation")
    text = str(text)
    _check_safe(text)
    parts = _split_parts(_normalise(text))
    if not parts:
        raise EquationError("enter an equation")
    if len(parts) > 2:
        raise EquationError("not supported: more than two equations")
    parsed = [_parse_part(p) for p in parts]

    if len(parsed) == 2:
        sides = {}
        for lhs, rhs in parsed:
            if lhs is None or lhs not in (_X, _Y) or lhs in sides:
                raise EquationError("not supported: system of equations (use x = f(t), y = g(t))")
            if _names(rhs) & {"x", "y"}:
                raise EquationError("parametric: right sides must not contain x or y")
            sides[lhs] = rhs
        fx, fy = sides[_X], sides[_Y]
        tex = f"x = {sp.latex(fx)},\\quad y = {sp.latex(fy)}"
        return _make(text, "parametric", ["t"], [fx, fy], {"t": (0.0, TWO_PI)}, tex)

    lhs, rhs = parsed[0]
    if lhs is not None:
        rn = _names(rhs)
        if lhs == _R and not rn & {"x", "y"}:
            return _make(text, "polar", ["theta"], [rhs], {"theta": (0.0, TWO_PI)},
                         f"r = {sp.latex(rhs)}")
        if lhs == _Z and "z" not in rn:
            return _make(text, "surface", ["x", "y"], [rhs], {"x": (-5.0, 5.0), "y": (-5.0, 5.0)},
                         f"z = {sp.latex(rhs)}")
        if lhs == _Y and "y" not in rn:
            return _make(text, "explicit", ["x"], [rhs], {"x": (-10.0, 10.0)},
                         f"y = {sp.latex(rhs)}")
        if (_names(lhs) | rn) & {"x", "y"}:
            return _make(text, "implicit", ["x", "y"], [lhs - rhs],
                         {"x": (-10.0, 10.0), "y": (-10.0, 10.0)},
                         f"{sp.latex(lhs)} = {sp.latex(rhs)}")
        raise EquationError("equation needs x or y (or r = f(theta), z = f(x, y))")

    e = rhs
    n = _names(e)
    if "y" in n:
        return _make(text, "implicit", ["x", "y"], [e], {"x": (-10.0, 10.0), "y": (-10.0, 10.0)},
                     f"{sp.latex(e)} = 0")
    if "x" not in n:
        only = [a for a in ("t", "theta") if a in n]
        if len(only) == 1:
            a = only[0]
            return _make(text, "explicit", [a], [e], {a: (0.0, TWO_PI)}, f"y = {sp.latex(e)}")
    return _make(text, "explicit", ["x"], [e], {"x": (-10.0, 10.0)}, f"y = {sp.latex(e)}")


def _make(text, kind, axes, exprs, domain, tex) -> Spec:
    free = set()
    for e in exprs:
        free |= _names(e)
    params = sorted(free - set(axes))
    syms = [_AX.get(a, sp.Symbol(a)) for a in axes] + [sp.Symbol(p) for p in params]
    try:
        funcs = [sp.lambdify(syms, e, modules="numpy") for e in exprs]
    except Exception:
        raise EquationError("could not compile this equation")
    return Spec(text=text, kind=kind, params=params, defaults={p: 1.0 for p in params},
                domain=dict(domain), latex=tex, _axes=list(axes), _exprs=list(exprs), _funcs=funcs)


# ---------------------------------------------------------------- sampling

def _eval(f, args, shape) -> np.ndarray:
    try:
        v = f(*args)
    except (ZeroDivisionError, OverflowError, ValueError, FloatingPointError):
        return np.full(shape, np.nan)
    except Exception:
        raise EquationError("could not evaluate this equation")
    v = np.asarray(v)
    if np.iscomplexobj(v):
        re_, im = v.real, v.imag
        v = np.where(np.abs(im) <= 1e-9 * np.maximum(1.0, np.abs(re_)), re_, np.nan)
    try:
        v = v.astype(float)
    except (TypeError, ValueError):
        raise EquationError("could not evaluate this equation")
    v = np.broadcast_to(v, shape).copy()
    v[~np.isfinite(v)] = np.nan
    return v


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) index ranges of consecutive True."""
    m = np.concatenate(([False], mask, [False])).astype(np.int8)
    d = np.diff(m)
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def _split_jumps_1d(y: np.ndarray, ymid: np.ndarray, breaks: np.ndarray) -> None:
    """Mark breaks[i] (between samples i and i+1) where the curve passes a pole.
    ymid holds f at the interval midpoints."""
    dy = np.abs(np.diff(y))
    ok = np.isfinite(dy)
    if ok.sum() < 3:
        return
    med = np.median(dy[ok])
    lo, hi = np.nanpercentile(y, [5, 95])
    span = max(hi - lo, 1e-12)
    big = ok & (dy > 20 * med + 1e-12 * span)
    flip = (y[:-1] * y[1:]) < 0
    avg = 0.5 * (y[:-1] + y[1:])
    off = ok & ~(np.abs(ymid - avg) <= span)          # midpoint far off the chord, or non-finite
    breaks |= (big & flip) | off


def _split_jumps_2d(P: np.ndarray, breaks: np.ndarray) -> None:
    d = np.hypot(*np.diff(P, axis=0).T)
    ok = np.isfinite(d)
    if ok.sum() < 3:
        return
    med = np.median(d[ok])
    lo = np.nanpercentile(P, 5, axis=0)
    hi = np.nanpercentile(P, 95, axis=0)
    diag = max(float(np.hypot(*(hi - lo))), 1e-12)
    breaks |= ok & (d > 50 * med + 1e-12 * diag) & (d > 0.25 * diag)


def _polylines(P: np.ndarray, breaks: np.ndarray | None = None):
    """Split (N,2) points at non-finite rows and at breaks; return (lines, closed)."""
    good = np.isfinite(P).all(axis=1)
    lines, closed = [], []
    for a, b in _runs(good):
        seg_breaks = [] if breaks is None else list(np.flatnonzero(breaks[a:b - 1]) + a + 1)
        cuts = [a] + seg_breaks + [b]
        for s, e in zip(cuts[:-1], cuts[1:]):
            if e - s >= 2:
                L = np.ascontiguousarray(P[s:e], dtype=float)
                lines.append(L)
                closed.append(_is_closed(L))
    return lines, closed


def _is_closed(L: np.ndarray) -> bool:
    if len(L) < 3:
        return False
    span = float(np.ptp(L, axis=0).max())
    return bool(span > 0 and np.hypot(*(L[0] - L[-1])) <= 1e-6 * span)


def _merge_domain(spec: Spec, domain) -> dict[str, tuple[float, float]]:
    d = dict(spec.domain)
    if domain:
        for k, v in domain.items():
            if k in d and v is not None:
                lo, hi = float(v[0]), float(v[1])
                if not (np.isfinite(lo) and np.isfinite(hi)) or lo == hi:
                    raise EquationError(f"invalid range for {k}")
                d[k] = (min(lo, hi), max(lo, hi))
    return d


def sample(spec: Spec, params: dict[str, float], domain: dict[str, tuple[float, float]] | None = None,
           n: int = 800) -> Result:
    params = params or {}
    pv = []
    for p in spec.params:
        try:
            v = float(params.get(p, spec.defaults.get(p, 1.0)))
        except (TypeError, ValueError):
            v = spec.defaults.get(p, 1.0)
        pv.append(v)
    dom = _merge_domain(spec, domain)
    n = max(int(n), 2)
    warns: list[str] = []
    X = Y = Z = None
    lines: list[np.ndarray] = []
    closed: list[bool] = []

    with np.errstate(all="ignore"):
        if spec.kind == "explicit":
            a = spec._axes[0]
            u = np.linspace(*dom[a], n)
            y = _eval(spec._funcs[0], [u] + pv, u.shape)
            um = 0.5 * (u[:-1] + u[1:])
            ymid = _eval(spec._funcs[0], [um] + pv, um.shape)
            breaks = np.zeros(n - 1, bool)
            _split_jumps_1d(y, ymid, breaks)
            lines, closed = _polylines(np.column_stack([u, y]), breaks)

        elif spec.kind in ("parametric", "polar"):
            a = spec._axes[0]
            u = np.linspace(*dom[a], n)
            if spec.kind == "parametric":
                px = _eval(spec._funcs[0], [u] + pv, u.shape)
                py = _eval(spec._funcs[1], [u] + pv, u.shape)
            else:
                r = _eval(spec._funcs[0], [u] + pv, u.shape)
                px, py = r * np.cos(u), r * np.sin(u)
            P = np.column_stack([px, py])
            breaks = np.zeros(n - 1, bool)
            _split_jumps_2d(P, breaks)
            lines, closed = _polylines(P, breaks)

        elif spec.kind == "implicit":
            lines, closed = _implicit(spec, pv, dom, min(n, 400), warns)

        elif spec.kind == "surface":
            m = max(min(n, 150), 2)
            xs = np.linspace(*dom["x"], m)
            ys = np.linspace(*dom["y"], m)
            X, Y = np.meshgrid(xs, ys)
            Z = _eval(spec._funcs[0], [X, Y] + pv, X.shape)
            if not np.isfinite(Z).any():
                warns.append("no real values in this range")
        else:
            raise EquationError(f"unknown kind {spec.kind}")

    if spec.kind != "surface" and not lines and not warns:
        warns.append("nothing to draw in this range")
    return Result(kind=spec.kind, polylines=lines, closed=closed, X=X, Y=Y, Z=Z, warnings=warns)


def _implicit(spec, pv, dom, m, warns):
    import contourpy

    m = max(m, 3)
    xs = np.linspace(*dom["x"], m)
    ys = np.linspace(*dom["y"], m)
    GX, GY = np.meshgrid(xs, ys)
    f = spec._funcs[0]
    F = _eval(f, [GX, GY] + pv, GX.shape)
    fin = np.isfinite(F)
    if not fin.any():
        warns.append("no real values in this range")
        return [], []
    if F[fin].min() > 0 or F[fin].max() < 0:
        return [], []
    gen = contourpy.contour_generator(xs, ys, np.ma.masked_invalid(F),
                                      line_type=contourpy.LineType.Separate)
    raw = gen.lines(0.0)
    # Drop spurious crossings where F jumps sign through a pole (e.g. y = 1/x as implicit):
    # a genuine zero-crossing vertex has small |F|, a pole crossing has huge |F|.
    tol = 0.1 * float(np.median(np.abs(F[fin]))) + 1e-12
    lines, closed = [], []
    for L in raw:
        L = np.asarray(L, float)
        if len(L) < 2:
            continue
        fv = _eval(f, [L[:, 0], L[:, 1]] + pv, (len(L),))
        bad = ~(np.abs(fv) <= tol)
        if bad.any():
            P = L.copy()
            P[bad] = np.nan
            ls, cs = _polylines(P)
        else:
            ls, cs = [L], [_is_closed(L)]
        lines += ls
        closed += cs
    return lines, closed
