import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

GREEN = "#1ea01e"
RED = "#dc1e1e"


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_weekly_defects(t, path):
    fig, ax = plt.subplots(figsize=(11, 4.5))
    bottom = np.zeros(len(t))
    for col in t.columns:
        values = t[col].to_numpy()
        ax.bar(t.index, values, width=6, bottom=bottom, label=col)
        bottom += values
    if t.shape[1]:
        ax.legend()
    ax.set_xlabel("week start")
    ax.set_ylabel("defect count")
    ax.set_title("Weekly defect composition")
    fig.autofmt_xdate()
    _save(fig, path)


def plot_fruit_volume(v, path):
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.arange(len(v))
    ax.bar(x, v["n"], color=RED, label="bad")
    ax.bar(x, v["good"], color=GREEN, label="good")
    ax.set_xticks(x)
    ax.set_xticklabels(v.index)
    ax.set_ylabel("inspected fruits")
    ax.set_title("Volume by fruit type")
    ax.legend()
    _save(fig, path)


def plot_growth(tables, path):
    fig, axes = plt.subplots(len(tables), 1, figsize=(10, 3.5 * len(tables)), squeeze=False)
    for ax, (name, g) in zip(axes[:, 0], tables.items()):
        ax.plot(g.index, g["good_growth_pct"], color=GREEN, marker="o", label="good")
        ax.plot(g.index, g["bad_growth_pct"], color=RED, marker="o", label="bad")
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_ylabel("growth vs previous period (%)")
        ax.set_title(f"{name} growth")
        ax.legend()
    _save(fig, path)


def plot_forecast(f, path):
    f = f.dropna(subset=["good_pred"])
    fig, ax = plt.subplots(figsize=(1.8 * len(f) + 3, 4.5))
    x = np.arange(len(f))
    w = 0.38
    for offset, name, color in ((-w / 2, "good", GREEN), (w / 2, "bad", RED)):
        pred = f[f"{name}_pred"].to_numpy()
        err = [pred - f[f"{name}_lo"].to_numpy(), f[f"{name}_hi"].to_numpy() - pred]
        ax.bar(x + offset, pred, w, yerr=err, capsize=3, color=color, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s}\nP(good>bad)={p:.2f}" for s, p in zip(f.index, f["p_good_gt_bad"])])
    ax.set_ylabel("forecast fruits per week (95% PI)")
    ax.set_title("Sector forecast")
    ax.legend()
    _save(fig, path)


def plot_recurrence(tables, path):
    fig, axes = plt.subplots(1, len(tables), figsize=(5 * len(tables), 4), squeeze=False)
    for ax, (by, t) in zip(axes[0], tables.items()):
        x = np.arange(len(t))
        w = 0.4
        ax.bar(x - w / 2, t["good_frac_up"], w, color=GREEN, label="good")
        ax.bar(x + w / 2, t["bad_frac_up"], w, color=RED, label="bad")
        ax.set_xticks(x)
        ax.set_xticklabels([str(i) for i in t.index], rotation=90 if by == "week" else 0)
        ax.set_ylim(0, 1)
        ax.set_ylabel("share of weeks with growth")
        ax.set_title(f"by {by}  (weeks per bucket: {int(t['good_n'].min())}-{int(t['good_n'].max())})")
    axes[0][0].legend()
    _save(fig, path)


def plot_gaussian(rates, summary, path, ncols=3):
    sectors = list(summary.index)
    nrows = -(-len(sectors) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.4 * nrows), squeeze=False)
    flat = axes.ravel()
    for ax in flat[len(sectors):]:
        ax.axis("off")
    for ax, sector in zip(flat, sectors):
        r = rates.xs(sector, level=0).to_numpy()
        row = summary.loc[sector]
        ax.hist(r, bins="auto", density=True, color="#999999")
        if row["std"] > 0:
            x = np.linspace(row["mean"] - 4 * row["std"], row["mean"] + 4 * row["std"], 200)
            ax.plot(x, stats.norm.pdf(x, row["mean"], row["std"]), color=RED)
        ax.set_title(f"{sector}: mean={row['mean']:.3f} sd={row['std']:.3f}\nShapiro p={row['shapiro_p']:.3f}  trend p={row['trend_p']:.3f}", fontsize=9)
        ax.set_xlabel("weekly bad rate")
    _save(fig, path)