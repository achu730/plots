"""Rebuild this figure from the data file, without Plotwise.

    python reproduce.py            # reads data/calculating_g.xlsx, writes figure_reproduced.pdf
Requires: numpy, pandas, matplotlib (and openpyxl for .xlsx).
Data SHA-256 when exported: 541e6a1546eef94ed970488078a7cb72a65ad7e1344cd94459901d698657169a
"""
import hashlib, json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---- Plotwise style helpers (verbatim copy) ----
"""Style helpers available to generated plot code as `pw`.

This file is self-contained (numpy + matplotlib only) so it can be inlined
into the exported reproduce.py script.
"""
import re

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

# Unit scale relative to a base unit of the same dimension.
UNITS = {
    # length (base m)
    "km": ("length", 1e3), "m": ("length", 1.0), "cm": ("length", 1e-2),
    "mm": ("length", 1e-3), "um": ("length", 1e-6), "µm": ("length", 1e-6),
    "μm": ("length", 1e-6), "nm": ("length", 1e-9),
    # time (base s)
    "s": ("time", 1.0), "ms": ("time", 1e-3), "us": ("time", 1e-6),
    "µs": ("time", 1e-6), "μs": ("time", 1e-6), "ns": ("time", 1e-9),
    "ps": ("time", 1e-12), "min": ("time", 60.0), "h": ("time", 3600.0),
    # energy (base eV)
    "ev": ("energy", 1.0), "kev": ("energy", 1e3), "mev": ("energy", 1e6),
    "gev": ("energy", 1e9), "tev": ("energy", 1e12),
    # mass in energy/c^2 (base eV/c^2)
    "ev/c2": ("mass", 1.0), "kev/c2": ("mass", 1e3), "mev/c2": ("mass", 1e6),
    "gev/c2": ("mass", 1e9), "tev/c2": ("mass", 1e12),
    # momentum (base eV/c)
    "ev/c": ("momentum", 1.0), "kev/c": ("momentum", 1e3), "mev/c": ("momentum", 1e6),
    "gev/c": ("momentum", 1e9),
    # mass (base kg)
    "kg": ("kgmass", 1.0), "g": ("kgmass", 1e-3), "mg": ("kgmass", 1e-6),
    # voltage, current, frequency
    "v": ("volt", 1.0), "mv": ("volt", 1e-3), "kv": ("volt", 1e3),
    "a": ("amp", 1.0), "ma": ("amp", 1e-3), "ua": ("amp", 1e-6), "µa": ("amp", 1e-6),
    "hz": ("freq", 1.0), "khz": ("freq", 1e3), "mhz": ("freq", 1e6), "ghz": ("freq", 1e9),
    # temperature (only scale-free use)
    "k": ("temp", 1.0),
    # spelled-out units as people type them in spreadsheet headers
    "meters": ("length", 1.0), "meter": ("length", 1.0), "metres": ("length", 1.0), "metre": ("length", 1.0),
    "centimeters": ("length", 1e-2), "millimeters": ("length", 1e-3),
    "seconds": ("time", 1.0), "second": ("time", 1.0), "sec": ("time", 1.0), "milliseconds": ("time", 1e-3),
}


def norm_unit(u):
    if u is None:
        return None
    u = str(u).strip().strip("[]()").strip()
    u = u.replace("$", "").replace("^{2}", "2").replace("^2", "2").replace("²", "2")
    u = u.replace("{", "").replace("}", "").replace("\\mu ", "µ").replace("\\mu", "µ")
    u = u.replace("\\mathrm", "").replace(" ", "")
    return u.lower() if u.lower() in UNITS else (u if u in UNITS else u.lower())


PRETTY = {"km": "km", "m": "m", "cm": "cm", "mm": "mm", "um": "µm", "µm": "µm", "μm": "µm", "nm": "nm",
          "s": "s", "ms": "ms", "us": "µs", "µs": "µs", "μs": "µs", "ns": "ns", "ps": "ps", "min": "min", "h": "h",
          "ev": "eV", "kev": "keV", "mev": "MeV", "gev": "GeV", "tev": "TeV", "kg": "kg", "g": "g", "mg": "mg",
          "v": "V", "mv": "mV", "kv": "kV", "a": "A", "ma": "mA", "ua": "µA", "µa": "µA",
          "hz": "Hz", "khz": "kHz", "mhz": "MHz", "ghz": "GHz", "k": "K",
          "meters": "m", "meter": "m", "metres": "m", "metre": "m", "centimeters": "cm", "millimeters": "mm",
          "seconds": "s", "second": "s", "sec": "s", "milliseconds": "ms"}


def pretty_unit(unit):
    """'gev/c^2' -> 'GeV/c²'; unknown units are returned unchanged."""
    n = norm_unit(unit)
    if n in UNITS:
        base, _, rest = n.partition("/")
        if base in PRETTY:
            return PRETTY[base] + ({"c2": "/c²", "c": "/c"}.get(rest, "/" + rest if rest else ""))
    return str(unit).strip()


def unit_factor(from_unit, to_unit):
    """Multiplicative factor to go from from_unit to to_unit, or None."""
    a, b = UNITS.get(norm_unit(from_unit)), UNITS.get(norm_unit(to_unit))
    if not a or not b or a[0] != b[0]:
        return None
    return a[1] / b[1]


def split_header(header):
    """'Y displacement (m)' -> ('Y displacement', 'm'); 'time_s' -> ('time', 's')."""
    h = str(header).strip()
    m = re.match(r"^(.*?)\s*[\[(]\s*([^\])]+?)\s*[\])]\s*$", h)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.*?)\s*/\s*([A-Za-zµμ/0-9^²]+)$", h)
    if m and norm_unit(m.group(2)) in UNITS:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.*)_([A-Za-zµμ]+)$", h)
    if m and norm_unit(m.group(2)) in UNITS:
        return m.group(1).replace("_", " ").strip(), m.group(2)
    return h, None


# ---- fits: the only curves the code may compute, always drawn as a labelled overlay and recorded ----
FIT_NAMES = {"linear": "Linear", "poly": "Polynomial", "exp": "Exponential", "log": "Logarithmic", "power": "Power",
             "gauss": "Gaussian"}
FIT_ALIASES = {"line": "linear", "straight": "linear", "lin": "linear", "polynomial": "poly", "quadratic": "poly",
               "cubic": "poly", "exponential": "exp", "logarithmic": "log", "ln": "log", "power-law": "power",
               "powerlaw": "power", "gaussian": "gauss", "normal": "gauss", "peak": "gauss"}
SUPS = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def fit_kind(kind, degree=None):
    k = str(kind or "linear").lower().strip()
    k = FIT_ALIASES.get(k, k)
    if k not in FIT_NAMES:
        raise ValueError(f"Unknown fit kind {kind!r}. Plotwise fits: linear, poly (degree 2-6), exp, log, power, gauss.")
    deg = {"quadratic": 2, "cubic": 3}.get(str(kind).lower(), degree)
    if k == "poly":
        deg = int(deg or 2)
        if not 1 <= deg <= 6:
            raise ValueError("A polynomial fit needs a degree from 1 to 6.")
        if deg == 1:
            k = "linear"
    return k, (1 if k == "linear" else deg if k == "poly" else None)


def _lsq(A, b, w):
    """Weighted linear least squares; returns (coefficients, covariance with sigma known)."""
    Aw, bw = A * w[:, None], b * w
    coef, *_ = np.linalg.lstsq(Aw, bw, rcond=None)
    cov = np.linalg.pinv(Aw.T @ Aw)
    return coef, cov


def _gauss(x, A, mu, sig, c):
    return A * np.exp(-0.5 * ((x - mu) / sig) ** 2) + c


def fit_model(kind, degree, x, y, e=None):
    """Least-squares fit of y(x). Returns (names, params, cov, f) with f(x, *params) the model.
    With uncertainties e the fit is weighted by 1/e and the errors are taken as known;
    without them every point counts equally and the errors are scaled by the scatter (like Excel's LINEST)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    w = np.ones_like(y) if e is None else 1.0 / np.asarray(e, float)
    if kind in ("linear", "poly"):
        A = np.vander(x, degree + 1)
        coef, cov = _lsq(A, y, w)
        names = [f"a{degree - i}" for i in range(degree + 1)] if degree > 1 else ["slope", "intercept"]
        return names, coef, cov, (lambda xx, *p: np.polyval(p, xx))
    if kind == "exp":  # y = a e^(b x)  ->  ln y = ln a + b x
        if (y <= 0).any():
            raise ValueError("An exponential fit needs every y value above 0.")
        coef, cov = _lsq(np.vander(x, 2), np.log(y), w * y)
        b, lna = coef
        J = np.array([[0, np.exp(lna)], [1, 0]])  # (a, b) from (b, ln a)
        return ["a", "b"], np.array([np.exp(lna), b]), J @ cov @ J.T, (lambda xx, a, b: a * np.exp(b * xx))
    if kind == "log":  # y = a + b ln x
        if (x <= 0).any():
            raise ValueError("A logarithmic fit needs every x value above 0.")
        coef, cov = _lsq(np.vander(np.log(x), 2), y, w)
        b, a = coef
        return ["a", "b"], np.array([a, b]), cov[::-1, ::-1], (lambda xx, a, b: a + b * np.log(xx))
    if kind == "power":  # y = a x^b  ->  ln y = ln a + b ln x
        if (x <= 0).any() or (y <= 0).any():
            raise ValueError("A power fit needs every x and y value above 0.")
        coef, cov = _lsq(np.vander(np.log(x), 2), np.log(y), w * y)
        b, lna = coef
        J = np.array([[0, np.exp(lna)], [1, 0]])
        return ["a", "b"], np.array([np.exp(lna), b]), J @ cov @ J.T, (lambda xx, a, b: a * np.power(xx, b))
    if kind == "gauss":  # y = A exp(-(x-mu)^2 / 2 sigma^2) + c, Levenberg-Marquardt from moment estimates
        c0 = float(np.min(y))
        A0 = float(np.max(y) - c0) or 1.0
        wt = np.clip(y - c0, 0, None)
        mu0 = float(np.sum(wt * x) / np.sum(wt)) if wt.sum() > 0 else float(x[np.argmax(y)])
        s0 = float(np.sqrt(np.sum(wt * (x - mu0) ** 2) / np.sum(wt))) if wt.sum() > 0 else float(np.ptp(x) / 4 or 1)
        p, lam = np.array([A0, mu0, max(s0, 1e-12 * max(1, abs(mu0))), c0]), 1e-3
        def resid(p):
            return (y - _gauss(x, *p)) * w
        def jac(p):
            A, mu, sig, c = p
            g = np.exp(-0.5 * ((x - mu) / sig) ** 2)
            return np.stack([g, A * g * (x - mu) / sig ** 2, A * g * (x - mu) ** 2 / sig ** 3, np.ones_like(x)], 1) * w[:, None]
        r = resid(p)
        for _ in range(200):
            J = jac(p)
            H = J.T @ J
            step = np.linalg.lstsq(H + lam * np.diag(np.diag(H) + 1e-300), J.T @ r, rcond=None)[0]
            pn = p + step
            rn = resid(pn)
            if np.sum(rn ** 2) < np.sum(r ** 2):
                p, r, lam = pn, rn, lam / 10
                if np.max(np.abs(step) / (np.abs(p) + 1e-12)) < 1e-10:
                    break
            else:
                lam *= 10
                if lam > 1e12:
                    break
        p[2] = abs(p[2])
        if not np.all(np.isfinite(p)) or p[2] == 0:
            raise ValueError("The Gaussian fit did not converge; the data may not have a peak to fit.")
        J = jac(p)
        return ["A", "mu", "sigma", "c"], p, np.linalg.pinv(J.T @ J), _gauss
    raise ValueError(f"Unknown fit kind {kind!r}")


def _num(v, e=None):
    """2.0312 ± 0.0213 -> '2.03 ± 0.02' (value rounded to its uncertainty)."""
    if e is not None and np.isfinite(e) and e > 0:
        d = max(0, -int(np.floor(np.log10(e))) + 1)
        if d <= 6 and abs(v) < 1e6:
            return f"({v:.{d}f} ± {e:.{d}f})"
        return f"({v:.3g} ± {e:.2g})"
    return f"{v:.4g}"


def fit_equation(kind, degree, params, errors, compact=False):
    """Full form with uncertainties for the log; compact form (3 significant figures) for the legend."""
    if compact:
        t = [f"{v:.3g}" for v in params]
        if kind in ("linear", "poly"):
            out = ""
            for i, v in enumerate(params):
                p_ = degree - i
                term = f"{abs(v):.3g}" + ("x" + (str(p_).translate(SUPS) if p_ > 1 else "") if p_ else "")
                out += (("−" if v < 0 else "") if not out else (" − " if v < 0 else " + ")) + term
            return "y = " + out
        if kind == "exp":
            return f"y = {t[0]}·e^({t[1]}x)"
        if kind == "log":
            return f"y = {t[0]} + {t[1]}·ln x"
        if kind == "power":
            return f"y = {t[0]}·x^{t[1]}"
        return f"µ = {t[1]}, σ = {abs(params[2]):.3g}"
    t = [_num(v, e) for v, e in zip(params, errors)]
    if kind in ("linear", "poly"):
        terms = []
        for i, c in enumerate(t):
            pw_ = degree - i
            terms.append(c + ("·x" + (str(pw_).translate(SUPS) if pw_ > 1 else "") if pw_ else ""))
        return "y = " + " + ".join(terms)
    if kind == "exp":
        return f"y = {t[0]}·e^({t[1]}·x)"
    if kind == "log":
        return f"y = {t[0]} + {t[1]}·ln x"
    if kind == "power":
        return f"y = {t[0]}·x^{t[1]}"
    return f"y = {t[0]}·exp(−(x − {t[1]})² / 2·{t[2]}²) + {t[3]}"


class Plotwise:
    """The `pw` object handed to generated code."""

    def __init__(self, style):
        self.style = style
        self.conversions = []  # declared unit conversions, read by the integrity check
        self.fits = []  # declared fits (pw.fit), checked and listed as changes by the integrity check
        self.colors = list((style.get("lines") or {}).get("colors") or ["#0072B2", "#D55E00", "#009E73"])
        self.linestyles = list((style.get("lines") or {}).get("styles") or ["-", "--", ":", "-."])

    # -- figure -----------------------------------------------------------
    def apply_rcparams(self):
        s = self.style
        font, axes = s.get("font", {}), s.get("axes", {})
        lines, legend = s.get("lines", {}), s.get("legend", {})
        rc = {
            "font.family": font.get("family", "serif"),
            "font.size": font.get("size_pt", 10),
            "axes.labelsize": font.get("label_size_pt", font.get("size_pt", 10)),
            "xtick.labelsize": font.get("tick_size_pt", font.get("size_pt", 10)),
            "ytick.labelsize": font.get("tick_size_pt", font.get("size_pt", 10)),
            "legend.fontsize": legend.get("fontsize_pt", font.get("size_pt", 10)),
            "legend.frameon": legend.get("frameon", False),
            "axes.linewidth": axes.get("linewidth", 1.0),
            "axes.grid": axes.get("grid", False),
            "lines.linewidth": lines.get("linewidth", 1.5),
            "xtick.direction": axes.get("ticks_direction", "in"),
            "ytick.direction": axes.get("ticks_direction", "in"),
            "xtick.top": axes.get("ticks_all_sides", False),
            "ytick.right": axes.get("ticks_all_sides", False),
            "xtick.minor.visible": axes.get("minor_ticks", False),
            "ytick.minor.visible": axes.get("minor_ticks", False),
            "axes.prop_cycle": mpl.cycler(color=self.colors),
            "mathtext.fontset": font.get("mathtext", "dejavusans"),
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.dpi": (s.get("figure") or {}).get("dpi", 300),
        }
        fam = rc["font.family"]
        names = font.get("names") or []
        if names:
            rc["font." + ("sans-serif" if fam == "sans-serif" else "serif" if fam == "serif" else "monospace")] = names
        mpl.rcParams.update(rc)

    def figsize(self, aspect=None, width_mm=None):
        f = self.style.get("figure", {})
        w = (width_mm or f.get("width_mm", 120)) / 25.4
        return (w, w * (aspect or f.get("aspect", 0.75)))

    def figure(self, nrows=1, ncols=1, aspect=None, width_mm=None, **kw):
        kw.setdefault("layout", "constrained")
        return plt.subplots(nrows, ncols, figsize=self.figsize(aspect, width_mm), **kw)

    # -- labels -----------------------------------------------------------
    def label(self, name, unit=None):
        if not unit:
            return name
        u = self.pretty_unit(unit)
        st = (self.style.get("labels") or {}).get("unit_style", "brackets")
        if st == "parentheses":
            return f"{name} ({u})"
        if st == "slash":
            return f"{name} / {u}"
        return f"{name} [{u}]"

    @staticmethod
    def pretty_unit(unit):
        return pretty_unit(unit)

    def experiment_label(self, ax, extra=None, loc=None):
        el = self.style.get("experiment_label")
        if not el:
            return None
        text = el.get("text", "")
        if extra:
            text = f"{text}\n{extra}" if el.get("extra_below", True) else f"{text} {extra}"
        loc = loc or el.get("loc", "upper right")
        x = 0.95 if "right" in loc else 0.05
        y = 0.93 if "upper" in loc else 0.07
        return ax.text(x, y, text, transform=ax.transAxes,
                       ha="right" if "right" in loc else "left",
                       va="top" if "upper" in loc else "bottom",
                       fontsize=el.get("fontsize_pt", 16), gid="pw-experiment-label")

    def legend(self, ax, loc=None, **kw):
        lg = self.style.get("legend") or {}
        kw.setdefault("frameon", lg.get("frameon", False))
        from matplotlib.container import ErrorbarContainer
        h, l = ax.get_legend_handles_labels()
        order = sorted(range(len(h)), key=lambda i: not isinstance(h[i], ErrorbarContainer))  # data first
        loc = loc or lg.get("loc", "best")
        el = self.style.get("experiment_label") or {}
        if el and loc == el.get("loc") and loc.startswith("upper") and "bbox_to_anchor" not in kw:
            # keep the legend clear of the experiment label in the same corner
            kw["bbox_to_anchor"] = (1.0 if "right" in loc else 0.0, 0.86)
        return ax.legend([h[i] for i in order], [l[i] for i in order], loc=loc, **kw)

    # -- data marks -------------------------------------------------------
    def data_style(self, i=0):
        d = self.style.get("data") or {}
        # a set data colour (e.g. black, as LHCb uses) goes to the first series; further series take the palette
        color = d.get("color") if (d.get("color") and i == 0) else self.colors[i % len(self.colors)]
        markers = ["o", "s", "^", "D", "v"]
        return dict(marker=markers[i % len(markers)] if i else d.get("marker", "o"),
                    ms=d.get("markersize", 4), color=color, ecolor=color,
                    capsize=d.get("capsize", 0), elinewidth=d.get("elinewidth", 1.0),
                    linestyle="none")

    def line_style(self, i=0):
        return dict(color=self.colors[i % len(self.colors)],
                    linestyle=self.linestyles[i % len(self.linestyles)],
                    lw=(self.style.get("lines") or {}).get("linewidth", 1.5))

    # -- units ------------------------------------------------------------
    def transform(self, values, factor=1.0, offset=0.0, axis=None, why=""):
        """Explicit, logged scaling value*factor by a constant from the file (e.g. time = frame / frame rate).
        Scaling by a factor is the only change to data values Plotwise allows; offsets are refused."""
        if offset:
            raise ValueError("Plotwise only allows scaling data by a factor; adding an offset is not allowed.")
        if not np.isfinite(float(factor)) or float(factor) == 0:
            raise ValueError("pw.transform needs a finite, non-zero factor.")
        self.conversions.append({"kind": "transform", "factor": float(factor), "axis": axis, "why": why})
        return np.asarray(values, dtype=float) * float(factor)

    def convert(self, values, from_unit, to_unit, axis=None):
        """Explicit, logged unit conversion. Use this instead of bare multiplications."""
        f = unit_factor(from_unit, to_unit)
        if f is None:
            raise ValueError(f"Cannot convert {from_unit!r} to {to_unit!r}")
        self.conversions.append({"from": from_unit, "to": to_unit, "factor": f, "axis": axis})
        return np.asarray(values, dtype=float) * f

    # -- fits -------------------------------------------------------------
    def fit(self, ax, x, y, kind="linear", yerr=None, degree=None, fit_range=None, label=None, color=None,
            show_equation=False, of=None, **kw):
        """Least-squares fit of the plotted data, drawn as a labelled line and recorded for the integrity check.
        This is the only way plot code may compute a curve; the data points themselves stay as they are.
        kind: "linear", "poly" (degree 2-6), "exp" (a·e^(b·x)), "log" (a + b·ln x), "power" (a·x^b),
        "gauss" (A·exp(-(x-mu)²/2sigma²) + c). yerr weights the fit (1/yerr) and gives a chi²/ndf.
        fit_range=(lo, hi) fits only the points with lo <= x <= hi. show_equation=True adds the equation and
        R² (or χ²/ndf) to the legend entry, like Excel's "Display equation on chart"; of="Trial A" names the
        data series in it. Returns the fit result as a dict; its "equation_short" is the text shown in the legend."""
        kind, degree = fit_kind(kind, degree)
        x, y = np.asarray(x, dtype=float).ravel(), np.asarray(y, dtype=float).ravel()
        e = None
        if yerr is not None:
            e = np.asarray(yerr, dtype=float)
            e = e.mean(axis=0) if e.ndim == 2 else e.ravel()  # asymmetric [lower, upper] -> mean
        use = np.isfinite(x) & np.isfinite(y) & (np.isfinite(e) & (e > 0) if e is not None else True)
        if fit_range is not None:
            lo, hi = fit_range
            use &= (x >= (-np.inf if lo is None else lo)) & (x <= (np.inf if hi is None else hi))
        xs, ys, es = x[use], y[use], (e[use] if e is not None else None)
        names, p, cov, f = fit_model(kind, degree, xs, ys, es)
        n, k = len(xs), len(p)
        if n <= k:
            raise ValueError(f"A {FIT_NAMES[kind].lower()} fit needs more than {k} points; it got {n}.")
        res = ys - f(xs, *p)
        chi2 = float(np.sum((res / es) ** 2)) if es is not None else None
        if es is None:
            cov = cov * float(np.sum(res ** 2)) / (n - k)  # errors from the scatter of the points
        errs = np.sqrt(np.clip(np.diag(cov), 0, None))
        sst = float(np.sum((ys - ys.mean()) ** 2))
        r2 = 1 - float(np.sum(res ** 2)) / sst if sst > 0 else None
        eq = fit_equation(kind, degree, p, errs)
        name = FIT_NAMES[kind] + (f" (degree {degree})" if kind == "poly" else "") + " fit"
        stat = (f"χ²/ndf = {chi2:.1f}/{n - k}" if chi2 is not None else f"R² = {r2:.4f}" if r2 is not None else "")
        short = {"linear": "Linear fit", "poly": f"Polynomial fit (degree {degree})", "exp": "Exponential fit",
                 "log": "Logarithmic fit", "power": "Power-law fit", "gauss": "Gaussian fit"}[kind]
        eq_short = fit_equation(kind, degree, p, errs, compact=True) + (f", {stat}" if stat else "")
        text = (label or (f"{of}: " + short[0].lower() + short[1:] if of else short)) \
            + (f"\n{eq_short}" if show_equation else "")
        lo, hi = float(xs.min()), float(xs.max())
        grid = np.geomspace(lo, hi, 300) if kind in ("log", "power") and lo > 0 else np.linspace(lo, hi, 300)
        gid = f"pw-fit-{len(self.fits)}"
        style = dict(self.line_style(len(self.fits)), linestyle="-")
        if color is not None:
            style["color"] = color
        style.update(kw)
        ax.plot(grid, f(grid, *p), label=text, gid=gid, **style)
        rec = {"gid": gid, "kind": kind, "degree": degree, "name": name, "params": dict(zip(names, map(float, p))),
               "errors": dict(zip(names, map(float, errs))), "chi2": chi2, "ndf": n - k, "r2": r2, "n_points": n,
               "weighted": es is not None, "fit_range": [lo, hi], "equation": eq, "equation_short": eq_short,
               "x": xs.tolist(), "y": ys.tolist(), "yerr": None if es is None else es.tolist()}
        self.fits.append(rec)
        lg = ax.get_legend()
        if lg is not None:  # a legend drawn before the fit is redrawn so the fit shows in it
            self.legend(ax, loc=lg._loc)
        elif show_equation:  # the equation lives in the legend, so make sure there is one
            self.legend(ax)
        return {k: v for k, v in rec.items() if k not in ("x", "y", "yerr")}

    def fit_plotted(self, ax, series=0, kind="linear", **kw):
        """Fit a data series already drawn on ax (series = its order among the data series), e.g. from the format panel."""
        from matplotlib.container import ErrorbarContainer
        found = []
        for c in ax.containers:
            if isinstance(c, ErrorbarContainer) and c.lines[0] is not None:
                xs, ys = c.lines[0].get_xdata(), c.lines[0].get_ydata()
                err = None
                for lc in c.lines[2]:
                    segs = lc.get_segments()
                    if len(segs) == len(xs) and all(len(sg) and abs(sg[0][0] - sg[-1][0]) <= 1e-12 * max(1, abs(sg[0][0])) for sg in segs):
                        err = np.array([[ys[i] - min(sg[0][1], sg[-1][1]) for i, sg in enumerate(segs)],
                                        [max(sg[0][1], sg[-1][1]) - ys[i] for i, sg in enumerate(segs)]])
                found.append((xs, ys, err, c.lines[0].get_color(), c.get_label()))
        done = {id(c.lines[0]) for c in ax.containers if isinstance(c, ErrorbarContainer)}
        for ln in ax.lines:
            if id(ln) not in done and ln.get_linestyle() in ("None", "", " ", "none") and ln.get_marker() not in (None, "", "None", " ", "none"):
                found.append((ln.get_xdata(), ln.get_ydata(), None, ln.get_color(), ln.get_label()))
        from matplotlib.collections import PathCollection
        for coll in ax.collections:  # ax.scatter(...)
            if isinstance(coll, PathCollection) and len(coll.get_offsets()):
                off = np.asarray(coll.get_offsets(), dtype=float)
                fc = coll.get_facecolors()
                found.append((off[:, 0], off[:, 1], None, tuple(fc[0]) if len(fc) else None, coll.get_label()))
        if not found:
            raise ValueError("There is no data series on this panel to fit.")
        if series >= len(found):
            raise ValueError(f"This panel has {len(found)} data series; series {series + 1} does not exist.")
        xs, ys, err, col, lab = found[series]
        kw.setdefault("yerr", err)
        kw.setdefault("color", col)
        if len(found) > 1 and lab and not str(lab).startswith("_"):
            kw.setdefault("of", lab)
        return self.fit(ax, xs, ys, kind=kind, **kw)

# ---- end helpers ----

# ---- Plotwise spreadsheet reader (verbatim copy) ----
"""Reads real-world spreadsheets and CSV files without assuming where anything is.

Every sheet is scanned for tables: a table is a run of mostly-numeric rows, and its header is the
text row (or two rows: names + units) directly above that run, wherever it sits. A sheet can hold
several tables (side by side, stacked with or without blank rows, titles or notes around them),
a separate table of uncertainties that is matched back to its values, and label/value notes such as
"Frame rate (fps) | 50". The spreadsheet row of every data row is kept for the integrity checks.
"""
import csv
import io
import os
import re

import numpy as np
import pandas as pd

UNC_RE = re.compile(r"\s*\(?\s*(uncertaint\w*|uncertatint\w*|uncert\w*|errors?|err|sigma|σ)\s*\)?\s*", re.I)
NO_UNC_RE = re.compile(r"\bno\s+uncert", re.I)
UNIT_CELL_RE = re.compile(r"^\s*[\[(]?\s*[A-Za-zµμΩ°%/^·*\d\-²³⁻¹ ]{1,14}\s*[\])]?\s*$")


def excel_row(df, r):
    """Spreadsheet row number of position r in df."""
    rows = df.attrs.get("rows")
    if rows and 0 <= int(r) < len(rows):
        return int(rows[int(r)])
    return int(df.attrs.get("first_row", 2)) + int(r)


def _num(v):
    """Number in the cell, or None. Accepts numbers stored as text, e.g. '3.2' or '1,5e-3'."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v) if np.isfinite(v) else None
    if isinstance(v, str):
        t = v.strip().replace("−", "-")
        if re.fullmatch(r"[-+]?(\d+[.,]?\d*|[.,]\d+)([eE][-+]?\d+)?", t):
            try:
                return float(t.replace(",", ".")) if t.count(",") == 1 and "." not in t else float(t.replace(",", ""))
            except ValueError:
                return None
    return None


def _filled(v):
    return v is not None and not (isinstance(v, str) and not v.strip()) and not (isinstance(v, float) and np.isnan(v))


def _col_letter(c):
    s = ""
    while c >= 0:
        s = chr(65 + c % 26) + s
        c = c // 26 - 1
    return s


def _clean(h):
    return re.sub(r"\s+", " ", str(h)).strip()


def _row_kind(cells):
    vals = [v for v in cells if _filled(v)]
    if not vals:
        return "empty"
    n_num = sum(_num(v) is not None for v in vals)
    if n_num == 0:
        return "text"
    return "num" if n_num >= 0.5 * len(vals) else "text"


def _column_groups(grid, ncols):
    """Column ranges separated by columns that are empty on the whole sheet."""
    used = [any(_filled(r[j]) for r in grid) for j in range(ncols)]
    groups, j = [], 0
    while j < ncols:
        if not used[j]:
            j += 1
            continue
        j0 = j
        while j < ncols and used[j]:
            j += 1
        groups.append((j0, j))
    return groups


def _header_from(text_rows, width):
    """Pick the header among the text rows just above a numeric run. Returns (names, title rows used)."""
    if not text_rows:
        return None, []
    last = text_rows[-1][1]
    filled_last = sum(_filled(v) for v in last)
    if len(text_rows) >= 2:
        prev = text_rows[-2][1]
        filled_prev = sum(_filled(v) for v in prev)
        units_like = filled_last >= 1 and all(UNIT_CELL_RE.match(str(v)) for v in last if _filled(v))
        if units_like and filled_prev >= filled_last and filled_prev >= 2:
            # two-row header: names on top, units below
            names = []
            for a, b in zip(prev, last):
                a, b = (_clean(a) if _filled(a) else ""), (_clean(b) if _filled(b) else "")
                if a and b:
                    names.append(a if b.strip("[]()") in a else f"{a} ({b.strip('[]()')})")
                else:
                    names.append(a or b)
            return names, [text_rows[-2][0], text_rows[-1][0]]
    if filled_last == 1 and width > 1:
        return None, []  # a single text cell above a wide table is a title, not a header
    return [_clean(v) if _filled(v) else "" for v in last], [text_rows[-1][0]]


def extract_constants(grid):
    """Find label/value pairs anywhere on the sheet ("Frame rate (fps) | 50", optionally followed by a unit
    or an uncertainty), record them, and blank their cells so they don't disturb table detection.
    A constant has one value: its row carries nothing else, and its value column has no data run above or below."""
    nrows = len(grid)
    ncols = len(grid[0]) if grid else 0
    cand = []
    for r in range(nrows):
        row = grid[r]
        for c in range(ncols):
            v = row[c]
            if not _filled(v) or _num(v) is not None or len(_clean(v)) < 2:
                continue
            c2 = None
            for k in range(c + 1, min(c + 4, ncols)):  # value may sit up to 2 empty cells to the right
                if _filled(row[k]):
                    c2 = k if _num(row[k]) is not None else None
                    break
            if c2 is None:
                continue
            extra_c = c2 + 1 if c2 + 1 < ncols and _filled(row[c2 + 1]) else None
            if extra_c is not None and extra_c + 1 < ncols and _filled(row[extra_c + 1]):
                continue  # more values follow: this is a table row, not a constant
            if extra_c is not None and _num(row[extra_c]) is None and not UNIT_CELL_RE.match(str(row[extra_c])):
                continue
            if c > 0 and _filled(row[c - 1]):
                continue  # a label glued to other cells on its left is part of a table row
            cand.append((r, c, c2, extra_c))
    keys = {(r, c2) for r, c, c2, e in cand}
    labels = {}
    for r, c, c2, e in cand:
        labels.setdefault((c, _clean(grid[r][c]).lower()), []).append(r)
    # a run of 3+ pairs under a header row with text over both columns is a small data table, not constants
    in_cand = {(r, c, c2) for r, c, c2, e in cand}
    headed = set()
    for r, c, c2, e in cand:
        if (r - 1, c, c2) in in_cand:
            continue
        run = r
        while (run + 1, c, c2) in in_cand:
            run += 1
        if r > 0 and run - r >= 2 and _filled(grid[r - 1][c]) and _filled(grid[r - 1][c2]) \
                and _num(grid[r - 1][c]) is None and _num(grid[r - 1][c2]) is None:
            headed |= {(rr, c, c2) for rr in range(r, run + 1)}
    consts = []
    for r, c, c2, e in cand:
        if (r, c, c2) in headed or len(labels[(c, _clean(grid[r][c]).lower())]) > 1:
            continue  # repeated labels are a category column (Air, Air, Oil...), not constants
        ok = True
        for rr in (r - 1, r + 1):
            if 0 <= rr < nrows:
                if _filled(grid[rr][c]) and _num(grid[rr][c]) is not None:
                    ok = False  # label sits inside a numeric column
                if _filled(grid[rr][c2]) and _num(grid[rr][c2]) is not None and (rr, c2) not in keys:
                    ok = False  # value is part of a column of data
        if not ok:
            continue
        item = {"Quantity": _clean(grid[r][c]), "Value": _num(grid[r][c2]), "Unit": "", "Uncertainty": np.nan,
                "Cell": f"{_col_letter(c2)}{r + 1}"}
        if e is not None:
            if _num(grid[r][e]) is not None:
                item["Uncertainty"] = _num(grid[r][e])
            else:
                item["Unit"] = _clean(grid[r][e]).strip("[]()")
        consts.append((r, item))
        for k in (c, c2, e):
            if k is not None:
                grid[r][k] = None
    consts.sort(key=lambda t: t[0])
    return [i for _, i in consts]


def find_tables(grid, sheet):
    """Return (tables, constants, notes) found in a 2-D list of cell values."""
    nrows = len(grid)
    ncols = max((len(r) for r in grid), default=0)
    grid = [list(r) + [None] * (ncols - len(r)) for r in grid]
    tables, notes = [], []
    consts = extract_constants(grid)
    for (j0, j1) in _column_groups(grid, ncols):
        sub = [r[j0:j1] for r in grid]
        kinds = [_row_kind(r) for r in sub]
        i = 0
        pending_text = []  # consecutive text rows seen just before the current position
        while i < nrows:
            k = kinds[i]
            if k == "empty":
                if pending_text and i + 1 < nrows and kinds[i + 1] == "empty":
                    pending_text = []
                i += 1
                continue
            if k == "text":
                pending_text.append((i, sub[i]))
                i += 1
                continue
            # a numeric run starts here; it ends at a text row or two blank rows in a row
            start = i
            rows = []
            while i < nrows and kinds[i] != "text":
                if kinds[i] == "num":
                    rows.append(i)
                elif i + 1 < nrows and kinds[i + 1] == "empty":
                    break
                i += 1
            width_used = [any(_filled(sub[r][c]) for r in rows) for c in range(j1 - j0)]
            # label/value notes: two used cells per row, text then number, and no header above
            per_row = [[v for v in sub[r] if _filled(v)] for r in rows]
            is_kv = all(len(p) == 2 and _num(p[0]) is None and _num(p[1]) is not None for p in per_row)
            header, used_rows = _header_from(pending_text[-2:] if pending_text else [], j1 - j0)
            if is_kv and (header is None or sum(bool(h) for h in header) < 2):
                for r, p in zip(rows, per_row):
                    c = next(c for c in range(j1 - j0) if _filled(sub[r][c]) and _num(sub[r][c]) is not None)
                    consts.append({"Quantity": _clean(p[0]), "Value": _num(p[1]), "Unit": "", "Uncertainty": np.nan,
                                   "Cell": f"{_col_letter(j0 + c)}{r + 1}"})
                pending_text = []
                continue
            cols = [c for c in range(j1 - j0) if width_used[c] or (header and header[c])]
            if not cols:
                pending_text = []
                continue
            names, seen = [], set()
            for c in cols:
                n = (header[c] if header and header[c] else f"column {_col_letter(j0 + c)}")
                while n in seen:
                    n += "'"
                seen.add(n)
                names.append(n)
            data = []
            for r in rows:
                row = []
                for c in cols:
                    v = sub[r][c]
                    nv = _num(v)
                    row.append(nv if nv is not None else (_clean(v) if _filled(v) else np.nan))
                data.append(row)
            df = pd.DataFrame(data, columns=names)
            df.attrs["rows"] = [r + 1 for r in rows]
            df.attrs["first_row"] = rows[0] + 1
            df.attrs["header_rows"] = [r + 1 for r in used_rows]
            rng = f"{_col_letter(j0 + cols[0])}{(used_rows[0] if used_rows else start) + 1}:{_col_letter(j0 + cols[-1])}{rows[-1] + 1}"
            df.attrs["range"] = rng
            titles = [_clean(" ".join(str(v) for v in t if _filled(v))) for (ti, t) in pending_text if ti not in used_rows]
            if titles:
                df.attrs["title"] = titles[-1]
            hdr = (f"header in row {used_rows[0] + 1}" + (f"-{used_rows[-1] + 1}" if len(used_rows) > 1 else "")
                   if used_rows else "no header row found, columns named by letter")
            gaps = (rows[-1] - rows[0] + 1) - len(rows)
            notes.append(f"'{sheet}': table at {rng}, {hdr}, data in rows {rows[0] + 1}-{rows[-1] + 1}"
                         + (f" ({gaps} blank row(s) skipped)" if gaps else "")
                         + (f", titled '{df.attrs['title']}'" if titles else "") + ".")
            tables.append(df)
            pending_text = []
    return _merge_side_by_side(tables), consts, notes


def _merge_side_by_side(tables):
    """Rejoin one table that was split by an empty spacer column (same header and data rows)."""
    out = []
    for df in tables:
        prev = out[-1] if out else None
        if prev is not None and prev.attrs.get("rows") == df.attrs.get("rows") and \
                prev.attrs.get("header_rows") == df.attrs.get("header_rows") and df.attrs.get("header_rows"):
            merged = pd.concat([prev, df], axis=1)
            merged.attrs = {**prev.attrs, "range": prev.attrs["range"].split(":")[0] + ":" + df.attrs["range"].split(":")[1]}
            out[-1] = merged
        else:
            out.append(df)
    return out


def _unc_base(h):
    """'Time (seconds) (uncertainties)' -> 'Time (seconds)'; None if the header isn't an uncertainty header."""
    h = _clean(h)
    if NO_UNC_RE.search(h) or not UNC_RE.search(h):
        return None
    return _clean(UNC_RE.sub(" ", h))


def _err_name(base):
    m = re.match(r"^(.*?)\s*([\[(][^\])]+[\])])\s*$", base)
    return f"{m.group(1)} error {m.group(2)}" if m else f"{base} error"


def _pair_uncertainties(tables, sheet, notes):
    """A table whose headers are '<name> (uncertainties)' for another table's columns becomes its error columns."""
    used = set()
    for a, dfa in enumerate(tables):
        for b, dfb in enumerate(tables):
            if a == b or a in used or b in used or len(dfa) != len(dfb):
                continue
            bases = {c: _unc_base(c) for c in dfb.columns}
            matched = {c: base for c, base in bases.items() if base in dfa.columns}
            if matched and len(matched) >= max(1, sum(1 for v in bases.values() if v) // 2):
                for c, base in matched.items():
                    dfa[_err_name(base)] = pd.to_numeric(dfb[c], errors="coerce").to_numpy()
                used.add(b)
                notes.append(f"'{sheet}': the table at {dfb.attrs['range']} holds uncertainties for the table at "
                             f"{dfa.attrs['range']}; added them as {len(matched)} error column(s).")
    return [t for k, t in enumerate(tables) if k not in used]


def _const_key(label):
    """'diameter of the ball in meters' / 'diameter of the ball (meters)' -> ('diameter of the ball', 'meters')."""
    s = _clean(label).lower()
    m = re.search(r"[\[(]([^\])]+)[\])]\s*$", s) or re.search(r"\s+in\s+([^\s()]+)\s*$", s)
    unit = m.group(1).strip() if m else ""
    return re.sub(r"\s+", " ", s[:m.start()] if m else s).strip(), unit


def _pair_constant_uncertainties(consts, sheet, notes):
    """'Frame rate uncertainties | 1' becomes the uncertainty of 'Frame rate (fps) | 50', so each constant keeps one row."""
    values = [c for c in consts if _unc_base(c["Quantity"]) is None]
    paired = []
    for u in consts:
        base = _unc_base(u["Quantity"])
        if base is None:
            continue
        name, unit = _const_key(base)
        hits = [c for c in values if _const_key(c["Quantity"])[0] == name
                and (not unit or not _const_key(c["Quantity"])[1] or _const_key(c["Quantity"])[1] == unit)
                and not np.isfinite(c["Uncertainty"])]
        if len(hits) == 1:
            hits[0]["Uncertainty"], hits[0]["Uncertainty cell"] = u["Value"], u["Cell"]
            paired.append(u)
    if paired:
        notes.append(f"'{sheet}': matched {len(paired)} uncertainty value(s) to their constants "
                     f"({', '.join(u['Quantity'] for u in paired[:2])}{', …' if len(paired) > 2 else ''}).")
    return [c for c in consts if all(c is not u for u in paired)]


def sheets_from_grids(grids):
    sheets, notes = {}, []
    for sheet, grid in grids:
        tables, consts, n = find_tables(grid, sheet)
        notes += n
        tables = _pair_uncertainties(tables, sheet, notes)
        for df in [t for t in tables if len(t) == 1 and t.attrs.get("header_rows")]:
            # a header row with a single row of values under it is a set of constants, one value each
            row = df.attrs["rows"][0]
            for k, col in enumerate(df.columns):
                v = df[col].iloc[0]
                if isinstance(v, (int, float)) and np.isfinite(v):
                    consts.append({"Quantity": col, "Value": float(v), "Unit": "", "Uncertainty": np.nan,
                                   "Cell": f"row {row}"})
            notes.append(f"'{sheet}': the one-row table at {df.attrs['range']} was read as constants.")
            tables = [t for t in tables if t is not df]
        for df in tables:
            name = sheet if len(tables) == 1 else f"{sheet} {df.attrs['range']}"
            df.attrs.update(sheet=sheet, single=len(tables) == 1)
            sheets[name] = df
        pair_notes = []
        consts = _pair_constant_uncertainties(consts, sheet, pair_notes)
        if consts:
            cdf = pd.DataFrame(consts)
            cdf = cdf.dropna(axis=1, how="all")
            if "Unit" in cdf and not cdf["Unit"].astype(bool).any():
                cdf = cdf.drop(columns="Unit")
            cdf.attrs["rows"] = [int(re.sub(r"\D", "", c["Cell"]) or 0) for c in consts]
            cdf.attrs.update(sheet=sheet, constants=True)
            sheets[f"{sheet} constants"] = cdf
            notes.append(f"'{sheet}': read {len(consts)} labelled value(s) outside the tables "
                         f"({', '.join(c['Quantity'] for c in consts[:3])}{', …' if len(consts) > 3 else ''}).")
        notes += pair_notes
    return sheets, notes


def _csv_grid(path):
    raw = open(path, encoding="utf-8-sig", errors="replace").read()
    try:
        dialect = csv.Sniffer().sniff(raw[:20000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [row for row in csv.reader(io.StringIO(raw), dialect)]
    # HEPData exports start with "#: key: value" lines; keep the table's description (or name) as its title
    meta = {}
    for i, row in enumerate(rows):
        m = re.match(r"^#:\s*([\w ]+?):\s*(.*)$", ",".join(row).strip())
        if m:
            meta.setdefault(m.group(1).lower(), (i, m.group(2).strip().strip('"')))
            rows[i] = []
    keep = meta.get("description") or meta.get("name")
    if keep and keep[1]:
        rows[max(i for i, _ in meta.values())] = [keep[1]]  # next to the header, where titles are looked for
    return rows


def read_table(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        grids = [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets]
    elif ext == ".xls":
        grids = [(str(k), v.where(pd.notna(v), None).values.tolist())
                 for k, v in pd.read_excel(path, sheet_name=None, header=None).items()]
    else:
        grids = [("data", _csv_grid(path))]
    sheets, notes = sheets_from_grids(grids)
    if not sheets:
        raise ValueError("No table of numbers was found in this file.")
    if ext not in (".xlsx", ".xlsm", ".xls"):
        # a CSV has no sheets: say "the CSV file" to people, keep the key "data" for the code
        for df in sheets.values():
            df.attrs["csv"] = True
        notes = [re.sub(r"^'data': (\w)", lambda m: m.group(1).upper(), n) for n in notes]
    return sheets, notes


def where(df, key=None):
    """How to name a table to people: "the CSV file", "sheet 'Sheet1'", "the table at A10:B16 of sheet 'Sheet1'"."""
    a = df.attrs
    sheet = a.get("sheet", key)
    if a.get("csv"):
        place = "the CSV file"
    else:
        place = f"sheet '{sheet}'"
    if a.get("constants"):
        return f"the constants in {place}"
    if a.get("single", True) or not a.get("range"):
        return place
    return f"the table at {a['range']} of {place}"

# ---- end reader ----

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data", 'calculating_g.xlsx')
EXPECTED_SHA256 = '541e6a1546eef94ed970488078a7cb72a65ad7e1344cd94459901d698657169a'
digest = hashlib.sha256(open(DATA, "rb").read()).hexdigest()
if digest != EXPECTED_SHA256:
    print("WARNING: data file differs from the one this figure was made from.")
data, _notes = read_table(DATA)  # same table finder Plotwise used
df = next(iter(data.values()))
style = json.load(open(os.path.join(HERE, "style.json"), encoding="utf-8"))
pw = Plotwise(style)
pw.apply_rcparams()

# ---- plot code (as generated and checked in Plotwise) ----
sheet = data["Sheet1"]

t = sheet["Time (seconds)"]
y = sheet["Y-displacement(meters)"]
t_err = sheet["Time error (seconds)"]
y_err = sheet["Y-displacement error (meters)"]

fig, ax = pw.figure()

data_kw = pw.data_style(0)
data_kw.update(zorder=3)  # keep data points drawn on top of the fit curve
ax.errorbar(t, y, xerr=t_err, yerr=y_err, **data_kw, label="Data")

pw.fit(ax, t, y, kind="poly", degree=2, yerr=y_err, label="2nd-order polynomial fit",
       show_equation=True)

ax.set_xlabel(pw.label("Time", "s"))
ax.set_ylabel(pw.label("Vertical displacement", "m"))

pw.legend(ax, loc="upper left")
# ---- end plot code ----

fig = globals().get("fig") or plt.gcf()
fig.savefig(os.path.join(HERE, "figure_reproduced.pdf"))
print("wrote figure_reproduced.pdf")
