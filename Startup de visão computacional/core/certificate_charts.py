import io
import threading

import numpy as np
from django.conf import settings
from matplotlib import font_manager, rc_context
from matplotlib.collections import PolyCollection
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator

from .certificate_text import T, bucket_label, clock, fill, name, num, pct, period_label, prob, signed_pct

MM = 1 / 25.4
DPI = 220
WIDTH = 174
INK = "#14231e"
MUTED = "#5b6b63"
GRID = "#e6e1d6"
AXIS = "#b9b2a3"
BAND1 = "#d9d3c4"
BAND2 = "#eeeae1"
GOOD = "#009E73"
POOR = "#E69F00"
ROTTEN = "#D55E00"
REVIEW = "#CC79A7"
UP = "#0072B2"
DOWN = "#E69F00"
HIST = "#0072B2"
DEFORMITY = {"podre": "#D55E00", "baixa_qualidade": "#E69F00", "queimada": "#CC79A7", "quebrada": "#0072B2"}
EXTRA = ["#56B4E9", "#8a8f8c"]
CLASSES = {"boa": GOOD, "baixa_qualidade": POOR, "podre": ROTTEN, "revisar": REVIEW}
FORECAST_WINDOW = 12
LOCK = threading.Lock()
FONT_DIR = settings.BASE_DIR / "assets" / "brand" / "fonts"
for _f in ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf"):
    if (FONT_DIR / _f).exists():
        font_manager.fontManager.addfont(str(FONT_DIR / _f))
FAMILY = ["Inter", "DejaVu Sans"] if (FONT_DIR / "Inter-Regular.ttf").exists() else ["DejaVu Sans"]
SEQ = LinearSegmentedColormap.from_list("fruitcam_seq", ["#e3f2ec", "#9fd3c3", "#3fab94", "#1f6f5f", "#0e3b31"])
VERDICT = {"aprovado": (GOOD, "o"), "reprovado": (ROTTEN, "D"), "inconclusivo": (POOR, "s"), "sem_dados": (MUTED, "x")}
RC = {
    "font.family": FAMILY,
    "font.size": 7.2,
    "axes.titlesize": 7.6,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlecolor": INK,
    "axes.labelsize": 7,
    "axes.labelcolor": MUTED,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.5,
    "xtick.labelsize": 6.4,
    "ytick.labelsize": 6.4,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.major.size": 2.2,
    "xtick.major.width": 0.6,
    "ytick.major.size": 0,
    "legend.fontsize": 6.6,
    "legend.frameon": False,
    "legend.handlelength": 1.4,
    "legend.borderaxespad": 0.2,
    "text.color": INK,
    "lines.linewidth": 1.3,
    "hatch.linewidth": 0.6,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
}
PCT = FuncFormatter(lambda v, _: pct(v, 0))
SPCT = FuncFormatter(lambda v, _: signed_pct(v, 0))
INT = FuncFormatter(lambda v, _: num(v))


class Chart:
    def __init__(self, png, width, height):
        self.png, self.width, self.height = png, width, height


def render(width, height, draw, *args):
    with LOCK, rc_context(RC):
        fig = Figure(figsize=(width * MM, height * MM), dpi=DPI)
        draw(fig, *args)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=DPI)
    return Chart(buf.getvalue(), width, height)


def values(xs):
    return np.array([np.nan if v is None else v for v in xs], dtype=float)


def ticks(ax, labels, period=None, most=10):
    n = len(labels)
    step = max(1, int(np.ceil(n / most)))
    pos = list(range(0, n, step))
    ax.set_xticks(pos)
    ax.set_xticklabels([period_label(labels[i], period) if period else labels[i] for i in pos])
    ax.set_xlim(-0.6, n - 0.4)


def bar_width(n):
    return 0.9 if n > 40 else 0.72


def gap(n):
    return {"edgecolor": "white", "linewidth": 0.5 if n > 40 else 0.9}


def bars(ax, x, h, width, bottom=None, color=None, label=None, n=None):
    x = np.asarray(x, float)
    h = np.nan_to_num(np.asarray(h, float))
    b = np.zeros_like(h) if bottom is None else np.asarray(bottom, float)
    left, right = x - width / 2, x + width / 2
    verts = np.stack([np.column_stack([left, b]), np.column_stack([left, b + h]), np.column_stack([right, b + h]), np.column_stack([right, b])], axis=1)
    ax.add_collection(PolyCollection(verts, facecolors=color, label=label, **gap(n or len(x))), autolim=True)
    ax.autoscale_view()


def framed(fig, left, width, bottom_mm=7, top_mm=2):
    h = fig.get_size_inches()[1] * 25.4
    return [left, bottom_mm / h, width, 1 - (bottom_mm + top_mm) / h]


def deformity_color(types):
    extra = iter(EXTRA)
    return {t: DEFORMITY.get(t) or next(extra, EXTRA[-1]) for t in types}


def robust_limit(xs, floor=0.05):
    xs = np.abs(values(xs))
    xs = xs[np.isfinite(xs)]
    if not len(xs):
        return floor, False
    top = max(floor, xs.max())
    if len(xs) < 12:
        return top, False
    q = max(floor, float(np.quantile(xs, 0.95)))
    return (q * 1.6, True) if top > q * 3 else (top, False)


def growth_limit(g):
    return robust_limit([v for k in ("good", "rotten") for key in ("count_growth", "prop_growth") for v in g[k][key]])


def volume_limit(o):
    return robust_limit([a + b for a, b in zip(o["good"], o["rotten"])], floor=1)


def clipped_labels(ax, x, v, m, text):
    mid = (np.min(x) + np.max(x)) / 2
    stack = {1: 0, -1: 0}
    for xi, vi in zip(x, v):
        if np.isfinite(vi) and abs(vi) > m:
            sign = 1 if vi > 0 else -1
            y = sign * m * (0.97 - 0.13 * stack[sign])
            stack[sign] += 1
            ax.text(xi, y, f" {text(vi)} {'▲' if vi > 0 else '▼'} ", ha="right" if xi > mid else "left", va="top" if vi > 0 else "bottom", fontsize=6, fontweight="bold", color=INK, bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.8}, zorder=6)


def overview_volume(fig, o, period):
    ax = fig.add_axes([0.075, 0.2, 0.91, 0.66])
    x = np.arange(len(o["labels"]))
    good, rotten = values(o["good"]), values(o["rotten"])
    bars(ax, x, good, bar_width(len(x)), color=GOOD, label=T["growth"]["good"])
    bars(ax, x, rotten, bar_width(len(x)), bottom=good, color=ROTTEN, label=T["growth"]["rotten"])
    m, clipped = volume_limit(o)
    ax.set_ylim(0, m if clipped else np.nanmax(good + rotten) * 1.05)
    if clipped:
        clipped_labels(ax, x, good + rotten, m, num)
    ticks(ax, o["labels"], period)
    ax.yaxis.set_major_formatter(INT)
    ax.yaxis.set_major_locator(MaxNLocator(5, integer=True))
    ax.set_ylabel(T["fruits"]["cols"][1].lower())
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)


def overview_rate(fig, o, period):
    ax = fig.add_axes([0.075, 0.16, 0.91, 0.74])
    good, rotten = values(o["good"]), values(o["rotten"])
    total = good + rotten
    rate = np.where(total > 0, rotten / np.where(total > 0, total, 1), np.nan)
    x = np.arange(len(rate))
    ax.fill_between(x, 0, rate, color=ROTTEN, alpha=0.1, linewidth=0)
    ax.plot(x, rate, color=ROTTEN, solid_capstyle="round", marker="o" if len(x) <= 30 else None, markersize=3.2, markeredgecolor="white", markeredgewidth=0.5)
    avg = o["rotten_rate"]
    ax.axhline(avg, color=INK, linewidth=0.8, linestyle=(0, (4, 3)))
    ax.text(-0.4, avg, fill(T["overview"]["avg"], v=pct(avg)), va="bottom", ha="left", fontsize=6.6, color=INK, bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6})
    ticks(ax, o["labels"], period)
    ax.set_ylim(0, max(0.05, np.nanmax(rate) * 1.18 if np.isfinite(rate).any() else 0.05))
    ax.yaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_locator(MaxNLocator(5))


def overview_sectors(fig, sectors):
    rows = sorted(sectors, key=lambda s: -s["rotten_rate"])
    ax = fig.add_axes(framed(fig, 0.16, 0.72))
    y = np.arange(len(rows))[::-1]
    rates = [s["rotten_rate"] for s in rows]
    ax.barh(y, rates, 0.6, color=[(ROTTEN, 1 if i == 0 else 0.45) for i in range(len(rows))])
    ax.set_yticks(y)
    ax.set_yticklabels([s["sector"] for s in rows])
    top = max(rates) if rates else 0.05
    for yi, s in zip(y, rows):
        ax.text(s["rotten_rate"] + top * 0.015, yi, f"{pct(s['rotten_rate'])} · n = {num(s['n'])}", va="center", fontsize=6.6, color=INK)
    ax.set_xlim(0, max(0.05, top * 1.32))
    ax.xaxis.set_major_formatter(PCT)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=6.8, labelcolor=INK)


def deformity(fig, d):
    ax = fig.add_axes([0.075, 0.16, 0.91, 0.68])
    weeks, types = d["weeks"], d["types"]
    colors = deformity_color(types)
    n = values(d["n_rotten"])
    x = np.arange(len(weeks))
    bottom = np.zeros(len(weeks))
    for t in types:
        share = np.where(n > 0, values(d["counts"][t]) / np.where(n > 0, n, 1), 0)
        bars(ax, x, share, bar_width(len(x)), bottom=bottom, color=colors[t], label=name("deformities", t))
        bottom += share
    ticks(ax, weeks, "week")
    ax.set_ylim(0, 1.0)
    ax.yaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=min(6, len(types)))


def fruits(fig, f):
    items = f["items"]
    ax = fig.add_axes(framed(fig, 0.12, 0.76))
    y = np.arange(len(items))[::-1]
    top = max([i["n"] for i in items] + [1])
    winners = [i["n"] == top and top > 0 for i in items]
    ax.barh(y, [i["n"] for i in items], 0.58, color=[(UP, 1 if w else 0.38) for w in winners])
    for yi, i, w in zip(y, items, winners):
        tag = f" · {T['fruits']['tie'] if f['tie'] else T['fruits']['winner']}" if w else ""
        ax.text(i["n"] + top * 0.015, yi, f"{num(i['n'])} ({pct(i['share'])}){tag}", va="center", fontsize=6.6, color=INK, fontweight="bold" if w else "normal")
    ax.set_yticks(y)
    ax.set_yticklabels([name("fruits", i["fruit"]) for i in items])
    ax.set_xlim(0, top * 1.38)
    ax.xaxis.set_major_formatter(INT)
    ax.xaxis.set_major_locator(MaxNLocator(5, integer=True))
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=6.8, labelcolor=INK)


def growth(fig, g, period):
    m, clipped = growth_limit(g)
    m *= 1.12
    axes = [fig.add_axes([0.085, 0.57, 0.9, 0.34]), fig.add_axes([0.085, 0.1, 0.9, 0.34])]
    for ax, kind in zip(axes, ("good", "rotten")):
        cg, pg = values(g[kind]["count_growth"]), values(g[kind]["prop_growth"])
        x = np.arange(len(cg))
        bars(ax, x, cg, bar_width(len(x)), color=[UP if v >= 0 else DOWN for v in np.nan_to_num(cg)])
        ax.plot(x, pg, color=INK, linewidth=0.8, linestyle=(0, (3, 2)))
        ax.axhline(0, color=MUTED, linewidth=0.7)
        if clipped:
            clipped_labels(ax, x, cg, m, signed_pct)
        for i in np.flatnonzero(np.isnan(cg)):
            ax.text(i, m * 0.04, T["na"], ha="center", va="bottom", fontsize=5.2, color=MUTED, rotation=90 if len(x) > 30 else 0)
        ticks(ax, g["labels"], period)
        ax.set_ylim(-m, m)
        ax.yaxis.set_major_formatter(SPCT)
        ax.yaxis.set_major_locator(MaxNLocator(5, symmetric=True))
        ax.set_title(T["growth"][kind], pad=3)
    handles = [Patch(color=UP, label=T["growth"]["up"]), Patch(color=DOWN, label=T["growth"]["down"]), Line2D([], [], color=INK, linewidth=0.8, linestyle=(0, (3, 2)), label=T["growth"]["prop"])]
    axes[0].legend(handles=handles, loc="lower right", bbox_to_anchor=(1, 1.0), ncol=3)


def recurring(fig, r, view):
    t = r[view]
    ax = fig.add_axes([0.085, 0.2, 0.9, 0.64])
    x = np.arange(len(t["buckets"]))
    w = 0.38 if len(x) <= 12 else 0.42
    good, rotten = values(t["good"]), values(t["rotten"])
    bars(ax, x - w / 2, good, w, color=GOOD, label=T["growth"]["good"], n=len(x) * 2)
    bars(ax, x + w / 2, rotten, w, color=ROTTEN, label=T["growth"]["rotten"], n=len(x) * 2)
    ax.axhline(0, color=MUTED, linewidth=0.7)
    labels = [bucket_label(view, b) for b in t["buckets"]]
    ticks(ax, labels, None, most=27 if view == "week" else 12)
    m, clipped = recurring_limit(r, view)
    m *= 1.3
    ax.set_ylim(-m, m)
    if clipped:
        clipped_labels(ax, x - w / 2, good, m, signed_pct)
        clipped_labels(ax, x + w / 2, rotten, m, signed_pct)
    for series, off in ((good, -w / 2), (rotten, w / 2)):
        if np.isfinite(series).any():
            k = int(np.nanargmax(series))
            v = min(series[k], m * 0.8)
            ax.text(k + off, v + (m * 0.03 if v >= 0 else -m * 0.03), f"{T['recurring']['peak']} {labels[k]} {signed_pct(series[k])}", ha="center", va="bottom" if v >= 0 else "top", fontsize=6, color=INK, bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6, "alpha": 0.85}, zorder=5)
    ax.yaxis.set_major_formatter(SPCT)
    ax.yaxis.set_major_locator(MaxNLocator(5, symmetric=True))
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)


def recurring_limit(r, view):
    return robust_limit(r[view]["good"] + r[view]["rotten"])


def gaussian(fig, s):
    poor = s["flagged"] and s["reasons"] != ["small_n"]
    ax = fig.add_axes([0.02, 0.15, 0.6, 0.7])
    qq = fig.add_axes([0.73, 0.15, 0.25, 0.7])
    edges, dens = np.array(s["hist"]["edges"]), np.array(s["hist"]["density"])
    xs, ys = np.array(s["pdf"]["x"]), np.array(s["pdf"]["y"])
    mu, sd = s["mean"], s["std"]
    lo, hi = min(edges[0], xs[0]), max(edges[-1], xs[-1])
    ax.axvspan(mu - 2 * sd, mu + 2 * sd, color=BAND2, linewidth=0, zorder=0)
    ax.axvspan(mu - sd, mu + sd, color=BAND1, linewidth=0, zorder=0)
    ax.bar(edges[:-1], dens, np.diff(edges), align="edge", color=HIST, alpha=0.55, edgecolor="white", linewidth=0.6, zorder=2, label=T["gaussian"]["hist"])
    ax.plot(xs, ys, color=MUTED if poor else INK, linestyle=(0, (3, 2)) if poor else "-", zorder=3, label=T["gaussian"]["pdf"])
    top = max(ys.max(), dens.max()) * 1.18
    white = {"facecolor": "white", "edgecolor": "none", "pad": 0.8}
    for a, b in ((lo, 0), (1, hi)):
        if a < b:
            ax.axvspan(a, b, facecolor="none", edgecolor=ROTTEN, hatch="////", linewidth=0, alpha=0.5, zorder=1)
            wide = (b - a) / (hi - lo) > 0.12
            ax.text((a + b) / 2, top * 0.45, T["gaussian"]["impossible"], ha="center", va="center", fontsize=6, color=INK, rotation=0 if wide else 90, bbox=white, zorder=5)
    ax.axvline(mu, color=INK, linewidth=0.9, zorder=4)
    ax.text(mu, top * 0.97, " " + fill(T["gaussian"]["mean"], v=pct(mu)), fontsize=6.4, color=INK, va="top", ha="left", bbox=white, zorder=5)
    for k in (1, 2):
        for sign in (-1, 1):
            x = mu + sign * k * sd
            if lo < x < hi:
                ax.text(x, top * 0.012, f"{'+' if sign > 0 else '−'}{k}σ", fontsize=5.6, color=MUTED, ha="center", va="bottom", bbox={**white, "pad": 0.4}, zorder=5)
    ax.set_xlim(lo, hi)
    ax.set_ylim(0, top)
    ax.xaxis.set_major_formatter(PCT)
    ax.xaxis.set_major_locator(MaxNLocator(6))
    ax.set_yticks([])
    ax.grid(False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    q = s["qq"]
    tx, ty = np.array(q["theoretical"]), np.array(q["observed"])
    ends = np.array([tx[0], tx[-1]])
    qq.plot(ends, q["intercept"] + q["slope"] * ends, color=MUTED, linewidth=0.8, label=T["gaussian"]["qq_line"])
    qq.scatter(tx, ty, s=7, color=ROTTEN if poor else HIST, edgecolors="white", linewidths=0.4, zorder=3)
    qq.yaxis.set_major_formatter(PCT)
    qq.yaxis.set_major_locator(MaxNLocator(4))
    qq.xaxis.set_major_locator(MaxNLocator(4))
    qq.set_xlabel(T["gaussian"]["theoretical"])
    qq.set_ylabel(T["gaussian"]["observed"])
    qq.set_title(T["gaussian"]["qq"], pad=3)
    qq.legend(loc="upper left", fontsize=5.8)
    if poor:
        stamp = f"{T['gaussian']['poor']}\n{shapiro(s['shapiro_p'])}"
        style = {"fontsize": 6, "fontweight": "bold", "color": INK, "bbox": {"facecolor": "white", "edgecolor": ROTTEN, "linewidth": 0.8, "boxstyle": "round,pad=0.3"}, "zorder": 6}
        ax.text(0.985, 0.95, stamp, transform=ax.transAxes, ha="right", va="top", **style)
        qq.text(0.98, 0.04, stamp, transform=qq.transAxes, ha="right", va="bottom", **style)


def shapiro(p):
    return "Shapiro p < 0,001" if p is not None and p < 0.001 else fill(T["gaussian"]["poor_sub"], p=num(p, 3))


def forecast_panel(ax, s, labels, target, period, min_periods, min_fruits):
    hist = values(s["history"])
    observed = np.flatnonzero(np.isfinite(hist))
    last = observed[-1] if len(observed) else len(hist) - 1
    start = max(0, min(len(hist) - FORECAST_WINDOW, last))
    window = list(range(start, len(hist)))
    x = np.arange(len(window) + 1)
    ok = s["status"] == "ok" and len(observed) > 0
    ax.axhline(0.5, color=MUTED, linewidth=0.7, linestyle=(0, (4, 3)))
    ax.text(x[-1] + 0.4, 0.5, T["forecast"]["half"], va="center", ha="left", fontsize=6, color=MUTED, bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6})
    ax.plot(x[:-1], hist[window], color=INK, marker="o", markersize=2.6, markeredgecolor="white", markeredgewidth=0.4, alpha=1 if ok else 0.35)
    if ok:
        li = last - start
        yl = hist[last]
        ax.fill_between([li, x[-1]], [yl, s["rotten_lo"]], [yl, s["rotten_hi"]], facecolor=(ROTTEN, 0.16 if s["reliable"] else 0.06), edgecolor=(ROTTEN, 0.5), linewidth=0, hatch=None if s["reliable"] else "////")
        ax.plot([li, x[-1]], [yl, s["rotten_pred"]], color=ROTTEN, linestyle=(0, (3, 2)))
        ax.errorbar([x[-1]], [s["rotten_pred"]], yerr=[[s["rotten_pred"] - s["rotten_lo"]], [s["rotten_hi"] - s["rotten_pred"]]], fmt="o", color=ROTTEN, markersize=3.6, markeredgecolor="white", markeredgewidth=0.5, elinewidth=0.8, capsize=2.2)
        arrow = "↑" if s["slope"] > 0 else "↓" if s["slope"] < 0 else "→"
        ax.text(0.02, 0.97, f"{fill(T['forecast']['pred'], arrow=arrow, v=pct(s['rotten_pred']))}\n{fill(T['forecast']['chance'], p=prob(s['p_more_rotten']))}", transform=ax.transAxes, va="top", ha="left", fontsize=6.2, color=INK, bbox={"facecolor": "white", "edgecolor": ROTTEN if not s["reliable"] else "none", "linewidth": 0.7, "pad": 1.6})
    else:
        head, _, tail = fill(T["forecast"]["empty"], n=s["n_periods"], min=min_periods, fruits=min_fruits).partition(": ")
        ax.text(0.5, 0.74, f"{head}\n{tail}", transform=ax.transAxes, ha="center", va="center", fontsize=6.4, color=INK, linespacing=1.4, bbox={"facecolor": BAND2, "edgecolor": "none", "pad": 3.5}, zorder=6)
    tick_labels = [period_label(labels[i], period) for i in window] + [period_label(target, period)]
    step = max(1, int(np.ceil(len(tick_labels) / 5)))
    pos = sorted(set(list(range(0, len(tick_labels), step)) + [len(tick_labels) - 1]))
    ax.set_xticks(pos)
    ax.set_xticklabels([tick_labels[i] for i in pos])
    ax.set_xlim(-0.5, x[-1] + 1.6)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_locator(MaxNLocator(4))
    ax.set_title(s["sector"], pad=3)


def forecast_row(fig, items, labels, target, period, min_periods, min_fruits):
    for i, s in enumerate(items):
        ax = fig.add_axes([0.07 + i * 0.5, 0.16, 0.4, 0.7])
        forecast_panel(ax, s, labels, target, period, min_periods, min_fruits)


def line_labels(c):
    daily = c["window_minutes"] >= 1440
    return [w["start"][8:10] + "/" + w["start"][5:7] if daily else clock(w["start"]) for w in c["windows"]]


def line_flow(fig, c):
    ax = fig.add_axes([0.075, 0.2, 0.91, 0.66])
    x = np.arange(len(c["windows"]))
    bottom = np.zeros(len(x))
    for k, color in CLASSES.items():
        v = np.array([w[k] for w in c["windows"]], dtype=float)
        bars(ax, x, v, bar_width(len(x)), bottom=bottom, color=color, label=name("classes", k))
        bottom += v
    ax.set_ylim(0, max(1, bottom.max()) * 1.05)
    ticks(ax, line_labels(c), None)
    ax.yaxis.set_major_formatter(INT)
    ax.yaxis.set_major_locator(MaxNLocator(5, integer=True))
    ax.set_ylabel(T["fruits"]["cols"][1].lower())
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4)


def line_pchart(fig, c):
    ax = fig.add_axes([0.075, 0.2, 0.91, 0.66])
    pc = c["p_chart"]
    x = np.arange(len(c["windows"]))
    p, ucl = values(pc["p"]), values(pc["ucl"])
    ax.fill_between(x, 0, ucl, step="mid", color=ROTTEN, alpha=0.07, linewidth=0)
    ax.step(x, ucl, where="mid", color=ROTTEN, linewidth=0.9, linestyle=(0, (4, 2)), label=T["line"]["ucl"])
    if pc["center"] is not None:
        ax.axhline(pc["center"], color=MUTED, linewidth=0.8, linestyle=(0, (2, 2)), label=T["line"]["center"])
    ax.plot(x, p, color=INK, linewidth=0.9, marker="o", markersize=2.2, markeredgecolor="white", markeredgewidth=0.3, label=T["line"]["points"])
    alarms = sorted({a["index"] for a in pc["alarms"]})
    if alarms:
        ax.scatter(alarms, p[alarms], marker="D", s=22, color=ROTTEN, edgecolors="white", linewidths=0.6, zorder=4, label=T["line"]["alarm"])
    ticks(ax, line_labels(c), None)
    top = np.nanmax(np.concatenate([p, ucl])) if np.isfinite(np.concatenate([p, ucl])).any() else 0.05
    ax.set_ylim(0, max(0.05, top * 1.15))
    ax.yaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4)


def coverage(fig, cv, period):
    counts = np.array(cv["counts"], float)
    sectors = cv["sectors"]
    ax = fig.add_axes([0.095, 0.2, 0.8, 0.72])
    cax = fig.add_axes([0.915, 0.2, 0.012, 0.72])
    cmap = SEQ.copy()
    cmap.set_bad("white")
    im = ax.imshow(np.ma.masked_where(counts <= 0, counts), aspect="auto", cmap=cmap, interpolation="nearest", norm=LogNorm(vmin=1, vmax=max(10, counts.max())))
    ax.set_yticks(range(len(sectors)))
    ax.set_yticklabels(sectors)
    ax.hlines(np.arange(len(sectors) + 1) - 0.5, -0.5, counts.shape[1] - 0.5, color="white", linewidth=1.4)
    ticks(ax, cv["labels"], period)
    ax.set_ylim(len(sectors) - 0.5, -0.5)
    ax.grid(False)
    ax.tick_params(axis="y", length=0, labelsize=6.6, labelcolor=INK)
    ax.spines["bottom"].set_visible(False)
    bar = fig.colorbar(im, cax=cax)
    bar.outline.set_visible(False)
    bar.ax.tick_params(labelsize=5.8, length=0)
    bar.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: num(v)))
    bar.set_label(T["coverage"]["legend"], fontsize=6, color=MUTED)


def lots(fig, c):
    items = c["lots"]
    ax = fig.add_axes([0.2, 0.14, 0.6, 0.78])
    y = np.arange(len(items))[::-1]
    top = max([l["rotten"]["ci95"][1] or 0 for l in items] + [c["max_rotten"] or 0]) * 1.12 or 0.05
    for yi, l in zip(y, items):
        color, marker = VERDICT.get(l["verdict"], (MUTED, "o"))
        lo, hi = l["rotten"]["ci95"]
        if lo is not None:
            ax.plot([lo, hi], [yi, yi], color=color, linewidth=2.4, solid_capstyle="round", zorder=2)
            ax.plot([l["rotten"]["share"]], [yi], marker=marker, color=color, markersize=5.2, markeredgecolor="white", markeredgewidth=0.7, zorder=3)
        ax.text(1.02, yi, T["line"]["verdicts"].get(l["verdict"], l["verdict"] or ""), transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=6.6, fontweight="bold", color=INK)
    if c["max_rotten"] is not None:
        ax.axvline(c["max_rotten"], color=INK, linewidth=0.9, linestyle=(0, (4, 3)), zorder=1)
        ax.text(c["max_rotten"], len(items) - 0.35, f" {fill(T['line_more']['max'], v=pct(c['max_rotten']))}", fontsize=6.2, color=INK, va="bottom")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{l['lot']}  (n = {num(l['n'])})" for l in items])
    ax.set_ylim(-0.7, len(items) - 0.1)
    ax.set_xlim(0, top)
    ax.xaxis.set_major_formatter(PCT)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0, labelsize=6.4, labelcolor=INK)


def sizes(fig, c):
    edges = np.array(c["size_hist"]["edges"], float)
    ax = fig.add_axes([0.085, 0.2, 0.89, 0.66])
    for k in ("boa", "baixa_qualidade", "podre"):
        v = np.array(c["size_hist"]["counts"][k], float)
        ax.fill_between(edges[:-1], 0, v, step="post", color=CLASSES[k], alpha=0.14, linewidth=0)
        ax.step(np.append(edges[:-1], edges[-1]), np.append(v, v[-1]), where="post", color=CLASSES[k], linewidth=1.2, label=name("classes", k))
    ax.set_xlim(edges[0], edges[-1])
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(INT)
    ax.yaxis.set_major_locator(MaxNLocator(5, integer=True))
    ax.set_xlabel(T["line_more"]["sizes_axis"])
    ax.set_ylabel(T["line_more"]["fruits_axis"])
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3)
