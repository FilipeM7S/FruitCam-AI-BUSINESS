import numpy as np
import pandas as pd
from scipy import stats

GOOD = ("nao_podre",)
REQUIRED = ["timestamp", "sector", "fruit", "label"]
SEASONS = {
    12: "verao", 1: "verao", 2: "verao",
    3: "outono", 4: "outono", 5: "outono",
    6: "inverno", 7: "inverno", 8: "inverno",
    9: "primavera", 10: "primavera", 11: "primavera",
}
FORECAST_COLUMNS = ["n_weeks", "good_pred", "good_lo", "good_hi", "bad_pred", "bad_lo", "bad_hi", "diff_pred", "p_good_gt_bad"]


def load_records(path):
    df = pd.read_csv(path, dtype={"sector": str, "fruit": str, "label": str, "lot": str})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    if df.empty:
        raise ValueError("no records")
    if df[REQUIRED].isna().any().any():
        raise ValueError("null values in required columns")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)


def period_counts(df, good=GOOD, freq="W", trim=True):
    period = df["timestamp"].dt.to_period(freq)
    is_good = df["label"].isin(good)
    c = df.groupby([period, is_good]).size().unstack(fill_value=0)
    c = c.rename(columns={True: "good", False: "bad"})
    full = pd.period_range(period.min(), period.max(), freq=freq)
    c = c.reindex(index=full, columns=["good", "bad"], fill_value=0)
    c.index = c.index.to_timestamp()
    return c.iloc[1:-1] if trim else c


def weekly_defects(df, good=GOOD):
    week = df["timestamp"].dt.to_period("W")
    t = df.groupby([week, df["label"]]).size().unstack(fill_value=0)
    t = t.drop(columns=[c for c in t.columns if c in good])
    t = t.reindex(pd.period_range(week.min(), week.max(), freq="W"), fill_value=0)
    t.index = t.index.to_timestamp()
    return t


def predominant_defect(t):
    n = t.sum(axis=1)
    if t.shape[1] == 0:
        return pd.DataFrame({"top": "none", "share": np.nan, "n_defects": n}, index=t.index)
    top = t.idxmax(axis=1).where(n > 0, "none")
    return pd.DataFrame({"top": top, "share": t.max(axis=1) / n.where(n > 0), "n_defects": n})


def fruit_volume(df, good=GOOD):
    v = df.assign(good=df["label"].isin(good)).groupby("fruit")["good"].agg(n="size", good="sum")
    v["share"] = v["n"] / v["n"].sum()
    return v.sort_values("n", ascending=False)


def growth(df, good=GOOD, freq="W", trim=True):
    c = period_counts(df, good, freq, trim)
    g = c.pct_change().replace([np.inf, -np.inf], np.nan) * 100
    return c.join(g.add_suffix("_growth_pct"))


def overall_growth(counts):
    if len(counts) < 2:
        raise ValueError("need at least 2 periods")
    first, last = counts.iloc[0], counts.iloc[-1]
    return (last - first) / first.replace(0, np.nan) * 100


def recurrence(df, good=GOOD, by="month", seasons=SEASONS, trim=True):
    g = growth(df, good, "W", trim)
    start = g.index
    key = {
        "week": start.isocalendar().week.to_numpy(),
        "month": start.month.to_numpy(),
        "season": start.month.map(seasons).to_numpy(),
    }[by]
    out = {}
    for name in ("good", "bad"):
        s = g[f"{name}_growth_pct"]
        out[f"{name}_n"] = s.groupby(key).count()
        out[f"{name}_frac_up"] = (s > 0).astype(float).where(s.notna()).groupby(key).mean()
        out[f"{name}_median_growth_pct"] = s.groupby(key).median()
    out = pd.DataFrame(out)
    if by == "season":
        out = out.reindex([s for s in dict.fromkeys(seasons.values()) if s in out.index])
    return out


def ols_forecast(y, steps=1, level=0.95):
    y = np.asarray(y, dtype=float)
    n = len(y)
    t = np.arange(n, dtype=float)
    t_mean = t.mean()
    sxx = ((t - t_mean) ** 2).sum()
    slope = ((t - t_mean) * (y - y.mean())).sum() / sxx
    intercept = y.mean() - slope * t_mean
    resid = y - (intercept + slope * t)
    dof = n - 2
    s = np.sqrt((resid ** 2).sum() / dof)
    t_new = n - 1 + steps
    mean = intercept + slope * t_new
    se = s * np.sqrt(1 + 1 / n + (t_new - t_mean) ** 2 / sxx)
    q = stats.t.ppf(0.5 + level / 2, dof)
    return mean, mean - q * se, mean + q * se, se, dof


def p_positive(mean, se, dof):
    if se == 0:
        return 1.0 if mean > 0 else 0.0 if mean < 0 else 0.5
    return float(stats.t.cdf(mean / se, dof))


def forecast(df, good=GOOD, min_weeks=8, steps=1, level=0.95, trim=True):
    if min_weeks < 3:
        raise ValueError("min_weeks must be >= 3")
    idx = period_counts(df, good, "W", trim).index
    rows = {}
    for sector, g in df.groupby("sector"):
        c = period_counts(g, good, "W", trim=False).reindex(idx, fill_value=0)
        row = dict.fromkeys(FORECAST_COLUMNS, np.nan)
        row["n_weeks"] = int((c.sum(axis=1) > 0).sum())
        if row["n_weeks"] >= min_weeks:
            gm, glo, ghi, _, _ = ols_forecast(c["good"], steps, level)
            bm, blo, bhi, _, _ = ols_forecast(c["bad"], steps, level)
            dm, _, _, dse, ddf = ols_forecast(c["good"] - c["bad"], steps, level)
            row.update(good_pred=gm, good_lo=glo, good_hi=ghi, bad_pred=bm, bad_lo=blo, bad_hi=bhi,
                       diff_pred=dm, p_good_gt_bad=p_positive(dm, dse, ddf))
        rows[sector] = row
    out = pd.DataFrame.from_dict(rows, orient="index")[FORECAST_COLUMNS]
    count_cols = ["good_pred", "good_lo", "good_hi", "bad_pred", "bad_lo", "bad_hi"]
    out[count_cols] = out[count_cols].clip(lower=0)
    out["target_week"] = idx[-1] + pd.Timedelta(weeks=steps)
    return out


def sector_rates(df, good=GOOD, min_fruits=30):
    week = df["timestamp"].dt.to_period("W")
    bad = ~df["label"].isin(good)
    t = bad.groupby([df["sector"], week]).agg(["size", "sum"])
    t = t[t["size"] >= min_fruits]
    return (t["sum"] / t["size"]).rename("bad_rate")


def gaussian_fit(rates):
    rows = {}
    for sector, s in rates.groupby(level=0):
        weeks = s.index.get_level_values(1).asi8
        r = s.to_numpy()
        n = len(r)
        sd = r.std(ddof=1) if n > 1 else np.nan
        fit = n >= 3 and sd > 0
        trend = stats.linregress(weeks, r) if fit else None
        rows[sector] = {
            "n_weeks": n,
            "mean": r.mean(),
            "std": sd,
            "shapiro_p": stats.shapiro(r).pvalue if fit else np.nan,
            "trend_per_week": trend.slope if fit else np.nan,
            "trend_p": trend.pvalue if fit else np.nan,
        }
    return pd.DataFrame.from_dict(rows, orient="index")