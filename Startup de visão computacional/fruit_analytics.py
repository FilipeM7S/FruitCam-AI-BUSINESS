import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter
from scipy import stats

GOOD_LABELS = ("nao_podre",)
FRUIT_TYPES = ("caju", "castanha", "melao")
SEASONS = {
    1: "summer", 2: "summer", 3: "summer",
    4: "autumn", 5: "autumn", 6: "autumn",
    7: "winter", 8: "winter", 9: "winter",
    10: "spring", 11: "spring", 12: "spring",
}
FREQ = {"week": "W", "month": "M"}
MIN_PERIODS = 8
MIN_FRUITS = 30
MIN_GAUSS_N = 20
ALPHA = 0.05
MAX_OUTSIDE = 0.01
FORECAST_COLUMNS = [
    "status", "n_periods", "slope", "intercept", "rotten_pred", "rotten_lo", "rotten_hi", "p_more_rotten",
    "bt_origins", "bt_mae", "bt_naive_mae", "bt_coverage", "bt_direction_acc",
]
GOOD_COLOR = "#2a78d6"
ROTTEN_COLOR = "#eb6834"
NEUTRAL_COLOR = "#4a3aa7"
DEFORMITY_COLORS = ("#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
INK = "#52514e"
GRID = "#e6e6e6"
DPI = 300


def to_events(raw, good_labels=GOOD_LABELS):
    required = ["timestamp", "sector", "fruit", "label"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    if raw.empty:
        raise ValueError("no events")
    if raw[required].isna().any().any():
        raise ValueError("null values in required columns")
    is_good = raw["label"].isin(good_labels)
    events = pd.DataFrame({
        "timestamp": pd.to_datetime(raw["timestamp"]),
        "sector": raw["sector"].astype(str),
        "fruit_type": raw["fruit"].astype(str),
        "is_good": is_good,
        "deformity_type": raw["label"].astype(str).where(~is_good),
    })
    return events.sort_values("timestamp", kind="stable").reset_index(drop=True)


def load_events(path, good_labels=GOOD_LABELS):
    return to_events(pd.read_csv(path, dtype={"sector": str, "fruit": str, "label": str}), good_labels)


def counts(events, period="week", seasons=SEASONS):
    if period == "season":
        m = counts(events, "month")
        name = pd.Series(m.index.month.map(seasons))
        start = name.ne(name.shift()).to_numpy()
        c = m.groupby(np.cumsum(start)).sum()
        c.index = m.index[start]
        return c
    p = events["timestamp"].dt.to_period(FREQ[period])
    c = events.groupby([p, events["is_good"]]).size().unstack(fill_value=0)
    c = c.reindex(columns=[True, False], fill_value=0).set_axis(["good", "rotten"], axis=1)
    return c.reindex(pd.period_range(p.min(), p.max(), freq=FREQ[period]), fill_value=0)


def rel_change(s):
    prev = s.shift(1)
    return (s - prev) / prev.where(prev != 0)


def growth(events, period="week", seasons=SEASONS):
    c = counts(events, period, seasons)
    total = c["good"] + c["rotten"]
    out = c.assign(total=total)
    for k in ("good", "rotten"):
        out[f"{k}_prop"] = c[k] / total.where(total > 0)
    for k in ("good", "rotten"):
        out[f"{k}_count_growth"] = rel_change(out[k].astype(float))
        out[f"{k}_prop_growth"] = rel_change(out[f"{k}_prop"])
    return out


def bucket(index, period, seasons=SEASONS):
    if period == "week":
        return index.start_time.isocalendar().week.to_numpy().astype(int)
    if period == "month":
        return index.month.to_numpy()
    return index.month.map(seasons).to_numpy()


def recurring_growth(events, period, seasons=SEASONS):
    g = growth(events, period, seasons)
    key = bucket(g.index, period, seasons)
    out = pd.DataFrame({
        "good_median_growth": g["good_count_growth"].groupby(key).median(),
        "rotten_median_growth": g["rotten_count_growth"].groupby(key).median(),
        "good_n": g["good_count_growth"].groupby(key).count(),
        "rotten_n": g["rotten_count_growth"].groupby(key).count(),
    })
    if period == "season":
        out = out.reindex([s for s in dict.fromkeys(seasons.values()) if s in out.index])
    return out


def deformity_counts(events):
    week = events["timestamp"].dt.to_period("W")
    full = pd.period_range(week.min(), week.max(), freq="W")
    bad = ~events["is_good"]
    if not bad.any():
        return pd.DataFrame(index=full)
    t = events[bad].groupby([week[bad], events.loc[bad, "deformity_type"]]).size().unstack(fill_value=0)
    return t.reindex(full, fill_value=0)


def dominant_deformity(t):
    n = t.sum(axis=1)
    if t.shape[1] == 0:
        return pd.DataFrame({"dominant": "none", "share": np.nan, "n_rotten": n, "tie": False}, index=t.index)
    top = t.max(axis=1)
    return pd.DataFrame({
        "dominant": t.idxmax(axis=1).where(n > 0, "none"),
        "share": top / n.where(n > 0),
        "n_rotten": n,
        "tie": (t.eq(top, axis=0).sum(axis=1) > 1) & (n > 0),
    })


def fruit_counts(events, start=None, end=None, fruits=FRUIT_TYPES):
    keep = pd.Series(True, index=events.index)
    if start is not None:
        keep &= events["timestamp"] >= pd.Timestamp(start)
    if end is not None:
        keep &= events["timestamp"] < pd.Timestamp(end)
    n = events.loc[keep, "fruit_type"].value_counts()
    n = n.reindex(list(dict.fromkeys([*fruits, *n.index])), fill_value=0)
    return pd.DataFrame({"n": n, "share": n / n.sum()}).sort_values("n", ascending=False, kind="stable")


def sector_proportions(events, period="week", min_fruits=MIN_FRUITS):
    p = events["timestamp"].dt.to_period(FREQ[period])
    full = pd.period_range(p.min(), p.max(), freq=FREQ[period])
    grp = events.groupby([p, events["sector"]])["is_good"]
    n = grp.size().unstack(fill_value=0).reindex(full, fill_value=0)
    rotten = n - grp.sum().unstack(fill_value=0).reindex(full, fill_value=0)
    return rotten / n.where(n >= min_fruits), n


def linear_fit(t, y, t_new):
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    slope, intercept = np.polyfit(t, y, 1)
    dof = len(y) - 2
    s = np.sqrt(np.sum((y - intercept - slope * t) ** 2) / dof)
    se = s * np.sqrt(1 + 1 / len(y) + (t_new - t.mean()) ** 2 / np.sum((t - t.mean()) ** 2))
    return intercept + slope * t_new, se, dof, slope, intercept


def p_above_half(mean, se, dof):
    if se == 0:
        return 0.5 if mean == 0.5 else float(mean > 0.5)
    return float(stats.t.sf((0.5 - mean) / se, dof))


def backtest(t, v, min_periods=MIN_PERIODS, level=0.95):
    err, naive, inside, direction = [], [], [], []
    for k in range(min_periods, len(v)):
        mean, se, dof, _, _ = linear_fit(t[:k], v[:k], t[k])
        q = stats.t.ppf(0.5 + level / 2, dof)
        err.append(abs(np.clip(mean, 0, 1) - v[k]))
        naive.append(abs(v[k - 1] - v[k]))
        inside.append(mean - q * se <= v[k] <= mean + q * se)
        direction.append((mean > 0.5) == (v[k] > 0.5))
    if not err:
        return {"bt_origins": 0}
    return {
        "bt_origins": len(err),
        "bt_mae": float(np.mean(err)),
        "bt_naive_mae": float(np.mean(naive)),
        "bt_coverage": float(np.mean(inside)),
        "bt_direction_acc": float(np.mean(direction)),
    }


def forecast(events, period="week", min_periods=MIN_PERIODS, min_fruits=MIN_FRUITS, level=0.95):
    if min_periods < 3:
        raise ValueError("min_periods must be >= 3")
    props, _ = sector_proportions(events, period, min_fruits)
    rows = {}
    for sector in props.columns:
        y = props[sector].to_numpy()
        t = np.flatnonzero(~np.isnan(y))
        v = y[t]
        row = {"status": "insufficient data", "n_periods": len(v)}
        if len(v) >= min_periods:
            mean, se, dof, slope, intercept = linear_fit(t, v, len(y))
            q = stats.t.ppf(0.5 + level / 2, dof)
            row.update(
                status="ok", slope=slope, intercept=intercept,
                rotten_pred=float(np.clip(mean, 0, 1)),
                rotten_lo=float(np.clip(mean - q * se, 0, 1)),
                rotten_hi=float(np.clip(mean + q * se, 0, 1)),
                p_more_rotten=p_above_half(mean, se, dof),
            )
            row.update(backtest(t, v, min_periods, level))
        rows[sector] = row
    out = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=FORECAST_COLUMNS)
    out["target_period"] = props.index[-1] + 1
    return out


def gaussian_fit(props, alpha=ALPHA, max_outside=MAX_OUTSIDE, min_n=MIN_GAUSS_N):
    rows = {}
    for sector in props.columns:
        x = props[sector].dropna().to_numpy()
        n = len(x)
        mean = x.mean() if n else np.nan
        std = x.std(ddof=1) if n > 1 else np.nan
        row = {"n": n, "mean": mean, "std": std, "shapiro_w": np.nan, "shapiro_p": np.nan, "mass_outside_01": np.nan}
        if n >= 3 and std > 0:
            w, p = stats.shapiro(x)
            row.update(shapiro_w=w, shapiro_p=p, mass_outside_01=stats.norm.cdf(0, mean, std) + stats.norm.sf(1, mean, std))
        reasons = [r for r, hit in (
            (f"n<{min_n}", n < min_n),
            ("std zero or undefined", not std > 0),
            (f"Shapiro p<{alpha}", row["shapiro_p"] < alpha),
            (f"mass outside [0,1]>{max_outside}", row["mass_outside_01"] > max_outside),
        ) if hit]
        row.update(flagged=bool(reasons), reason="; ".join(reasons) or "ok")
        rows[sector] = row
    return pd.DataFrame.from_dict(rows, orient="index")


def period_labels(index, period, seasons=SEASONS):
    if period == "season":
        return [f"{seasons[p.month]} {p.year}" for p in index]
    if period == "week":
        return [str(p.start_time.date()) for p in index]
    return [str(p) for p in index]


def _fig(nrows=1, ncols=1, w=9, h=4.5):
    fig, axes = plt.subplots(nrows, ncols, figsize=(w, h), squeeze=False, facecolor="white")
    for ax in axes.ravel():
        ax.set_facecolor("white")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
    return fig, axes


def _xticks(ax, labels, max_ticks=10):
    pos = np.arange(0, len(labels), max(1, -(-len(labels) // max_ticks)))
    ax.set_xticks(pos)
    ax.set_xticklabels([labels[i] for i in pos], rotation=45, ha="right", fontsize=8)


def _prob(p):
    return "> 0.99" if p > 0.99 else "< 0.01" if p < 0.01 else f"= {p:.2f}"


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)


def plot_deformity(t, path):
    share = t.div(t.sum(axis=1).where(lambda s: s > 0), axis=0).fillna(0)
    fig, axes = _fig(w=11)
    ax = axes[0, 0]
    x = np.arange(len(share))
    bottom = np.zeros(len(share))
    for i, col in enumerate(share.columns):
        ax.bar(x, share[col], 0.8, bottom=bottom, color=DEFORMITY_COLORS[i % len(DEFORMITY_COLORS)], label=col, edgecolor="white", linewidth=0.5)
        bottom += share[col].to_numpy()
    _xticks(ax, period_labels(share.index, "week"))
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlabel("Week starting")
    ax.set_ylabel("Share of rotten fruit")
    ax.set_title("Weekly deformity mix among rotten fruit (empty bar = no rotten fruit)")
    if share.shape[1]:
        ax.legend(title="Deformity", frameon=False, bbox_to_anchor=(1.01, 1), loc="upper left")
    _save(fig, path)


def plot_forecast(props, fc, path, period="week", ncols=3):
    sectors = list(props.columns)
    ncols = min(ncols, len(sectors))
    nrows = -(-len(sectors) // ncols)
    fig, axes = _fig(nrows, ncols, 5 * ncols, 3.8 * nrows)
    for ax in axes.ravel()[len(sectors):]:
        ax.axis("off")
    labels = period_labels(props.index, period) + [str(fc["target_period"].iloc[0])]
    for ax, sector in zip(axes.ravel(), sectors):
        y = props[sector].to_numpy()
        x = np.arange(len(y))
        row = fc.loc[sector]
        ax.plot(x, y, "o", ms=4, color=ROTTEN_COLOR, label="Observed")
        ax.axhline(0.5, color=INK, linestyle="--", linewidth=0.8)
        if row["status"] == "ok":
            xs = np.arange(len(y) + 1)
            ax.plot(xs, row["intercept"] + row["slope"] * xs, color=INK, linewidth=1.5, label="Linear trend")
            ax.errorbar(len(y), row["rotten_pred"], yerr=[[row["rotten_pred"] - row["rotten_lo"]], [row["rotten_hi"] - row["rotten_pred"]]],
                        fmt="s", ms=7, color=INK, capsize=4, label="Forecast, 95% PI")
            ax.set_title(f"{sector}: P(rotten > good next {period}) {_prob(row['p_more_rotten'])}\n"
                         f"backtest MAE {row['bt_mae']:.3f} (naive {row['bt_naive_mae']:.3f})", fontsize=9)
        else:
            ax.set_title(f"{sector}: insufficient data ({row['n_periods']} periods)", fontsize=9)
        _xticks(ax, labels, 6)
        ax.set_ylim(0, 1)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_ylabel("Rotten proportion")
    axes[0, 0].legend(frameon=False, fontsize=8, loc="upper left")
    _save(fig, path)


def plot_fruit_counts(c, path):
    fig, axes = _fig(w=6)
    ax = axes[0, 0]
    x = np.arange(len(c))
    ax.bar(x, c["n"], 0.6, color=NEUTRAL_COLOR)
    for xi, (n, s) in zip(x, zip(c["n"], c["share"])):
        ax.text(xi, n, f"{n:,} ({s:.0%})" if n else "0", ha="center", va="bottom", fontsize=9, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(c.index)
    ax.set_ylabel("Fruits received")
    ax.set_title("Fruits received by type")
    _save(fig, path)


def plot_growth(g, kind, path, period="week", seasons=SEASONS):
    color = GOOD_COLOR if kind == "good" else ROTTEN_COLOR
    fig, axes = _fig(w=10)
    ax = axes[0, 0]
    x = np.arange(len(g))
    ax.plot(x, g[f"{kind}_count_growth"], "-o", ms=4, color=color, label="Growth of count")
    ax.plot(x, g[f"{kind}_prop_growth"], "--s", ms=4, color=color, mfc="white", label="Growth of proportion")
    ax.axhline(0, color=INK, linewidth=0.8)
    _xticks(ax, period_labels(g.index, period, seasons))
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel(f"Change vs previous {period}")
    ax.set_title(f"{kind.capitalize()} fruit: {period}-over-{period} growth (gaps = previous period was 0 or empty)")
    ax.legend(frameon=False)
    _save(fig, path)


def plot_recurring(tables, path):
    fig, axes = _fig(1, len(tables), 5.5 * len(tables), 4.5)
    for ax, (period, t) in zip(axes[0], tables.items()):
        x = np.arange(len(t))
        ax.bar(x - 0.2, t["good_median_growth"], 0.4, color=GOOD_COLOR, label="Good")
        ax.bar(x + 0.2, t["rotten_median_growth"], 0.4, color=ROTTEN_COLOR, label="Rotten")
        ax.axhline(0, color=INK, linewidth=0.8)
        _xticks(ax, [str(i) for i in t.index], 13 if period != "week" else 14)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        n = t["rotten_n"]
        ax.set_title(f"By {'week of year' if period == 'week' else period}  (periods per bar: {n.min()}-{n.max()})", fontsize=10)
        ax.set_ylabel("Median count growth")
    axes[0, 0].legend(frameon=False)
    _save(fig, path)


def plot_gaussian(props, fit, path, period="week"):
    sectors = list(fit.index)
    fig, axes = _fig(len(sectors), 2, 10, 3.4 * len(sectors))
    for (ax_h, ax_q), sector in zip(axes, sectors):
        x = props[sector].dropna().to_numpy()
        row = fit.loc[sector]
        verdict = f"FLAGGED: {row['reason']}" if row["flagged"] else "no flag raised"
        if len(x) < 3 or not row["std"] > 0:
            ax_h.set_title(f"{sector}: {verdict}", fontsize=9)
            ax_q.axis("off")
            continue
        ax_h.hist(x, bins="auto", density=True, color="#b9b8b3", edgecolor="white")
        xs = np.linspace(row["mean"] - 4 * row["std"], row["mean"] + 4 * row["std"], 300)
        ax_h.plot(xs, stats.norm.pdf(xs, row["mean"], row["std"]), color=ROTTEN_COLOR, linewidth=2, label="Fitted Gaussian")
        for b in (0, 1):
            if xs[0] < b < xs[-1]:
                ax_h.axvline(b, color=INK, linestyle=":", linewidth=1)
        ax_h.set_xlabel(f"Rotten proportion per {period}")
        ax_h.set_ylabel("Density")
        ax_h.set_title(f"{sector}: mean={row['mean']:.3f} std={row['std']:.3f} n={row['n']}\n{verdict}", fontsize=9)
        (osm, osr), (slope, intercept, _) = stats.probplot(x, dist="norm")
        ax_q.plot(osm, osr, "o", ms=4, color=ROTTEN_COLOR)
        ax_q.plot(osm, intercept + slope * osm, color=INK, linewidth=1.5)
        ax_q.set_xlabel("Theoretical normal quantile")
        ax_q.set_ylabel("Observed quantile")
        ax_q.set_title(f"Q-Q plot, Shapiro-Wilk W={row['shapiro_w']:.3f} p={row['shapiro_p']:.3f}", fontsize=9)
    _save(fig, path)


def run(events, out_dir, period="week", seasons=SEASONS, min_periods=MIN_PERIODS, min_fruits=MIN_FRUITS, start=None, end=None):
    os.makedirs(out_dir, exist_ok=True)
    defs = deformity_counts(events)
    props, _ = sector_proportions(events, period, min_fruits)
    res = {
        "deformity": dominant_deformity(defs),
        "forecast": forecast(events, period, min_periods, min_fruits),
        "fruits": fruit_counts(events, start, end),
        "growth": growth(events, period, seasons),
        "recurring": {p: recurring_growth(events, p, seasons) for p in ("week", "month", "season")},
        "gaussian": gaussian_fit(props),
    }
    path = lambda name: os.path.join(out_dir, name)
    plot_deformity(defs, path("1_deformity_weekly.png"))
    plot_forecast(props, res["forecast"], path("2_sector_forecast.png"), period)
    plot_fruit_counts(res["fruits"], path("3_fruit_counts.png"))
    plot_growth(res["growth"], "good", path("4_good_growth.png"), period, seasons)
    plot_growth(res["growth"], "rotten", path("5_rotten_growth.png"), period, seasons)
    plot_recurring(res["recurring"], path("6_recurring_growth.png"))
    plot_gaussian(props, res["gaussian"], path("7_sector_gaussian.png"), period)
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("records")
    parser.add_argument("out_dir")
    parser.add_argument("--period", choices=list(FREQ), default="week")
    parser.add_argument("--min-periods", type=int, default=MIN_PERIODS)
    parser.add_argument("--min-fruits", type=int, default=MIN_FRUITS)
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()
    res = run(load_events(args.records), args.out_dir, args.period, SEASONS, args.min_periods, args.min_fruits, args.start, args.end)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    for name in ("deformity", "forecast", "fruits", "growth", "gaussian"):
        print(f"\n== {name}\n{res[name].to_string()}")
    for p, t in res["recurring"].items():
        print(f"\n== recurring growth by {p}\n{t.to_string()}")
    print(f"\ncharts written to {args.out_dir}")


if __name__ == "__main__":
    main()
