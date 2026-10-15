import numpy as np
import pandas as pd
from django.conf import settings
from django.db import connection
from django.db.models import CharField
from django.db.models.functions import Cast
from django.utils import timezone
from scipy import stats as st

from analytics import fruit_analytics as FA

from . import rollups
from .models import Event

COLUMNS = ["timestamp", "sector", "fruit_type", "is_good", "deformity_type"]
RELIABLE_PERIODS = FA.MIN_GAUSS_N


def scope(source="real", sector=None, start=None, end=None):
    qs = Event.objects.all()
    if source != "all":
        qs = qs.filter(is_demo=source == "demo")
    if sector:
        qs = qs.filter(sector=sector)
    if start:
        qs = qs.filter(timestamp__gte=start)
    if end:
        qs = qs.filter(timestamp__lt=end)
    return qs


def rows(qs, columns):
    sql, params = qs.values_list(Cast("timestamp", CharField()), *columns[1:]).query.sql_with_params()
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        df = pd.DataFrame(cursor.fetchall(), columns=columns)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601").dt.tz_convert(settings.TIME_ZONE).dt.tz_localize(None)
    return df


def load_events(source="real", sector=None, start=None, end=None):
    df = rows(scope(source, sector, start, end).filter(needs_review=False), [*COLUMNS, "is_demo"])
    has_demo = bool(df["is_demo"].astype(bool).any())
    df["is_good"] = df["is_good"].astype(bool)
    return df[COLUMNS].sort_values("timestamp", kind="stable").reset_index(drop=True), has_demo


def load(source="real", sector=None, start=None, end=None):
    tz = timezone.get_current_timezone()
    if rollups.usable(start) and rollups.midnight(start, tz) and rollups.midnight(end, tz):
        return rollups.days(source, sector, start, end)
    return load_events(source, sector, start, end)


def total(events):
    return int(events["n"].sum()) if "n" in events.columns else len(events)


def weights(events):
    return events["n"] if "n" in events.columns else pd.Series(1, index=events.index)


def tally(events, column):
    if "n" not in events.columns:
        return events[column].value_counts()
    return events["n"].groupby(events[column]).sum().sort_values(ascending=False, kind="stable")


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray, pd.Series, pd.Index)):
        return [clean(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if np.isfinite(x) else None
    if x is None or x is pd.NA or x is pd.NaT:
        return None
    if isinstance(x, pd.Period):
        return str(x)
    return x


def deformity(events, period):
    t = FA.deformity_counts(events)
    d = FA.dominant_deformity(t)
    n = int(d["n_rotten"].sum())
    return {
        "status": "ok" if n else "no_data",
        "n": n,
        "weeks": FA.period_labels(t.index, "week"),
        "types": list(t.columns),
        "counts": {c: t[c] for c in t.columns},
        "dominant": d["dominant"],
        "share": d["share"],
        "tie": d["tie"],
        "n_rotten": d["n_rotten"],
    }


def forecast(events, period):
    props, n = FA.sector_proportions(events, period)
    fc = FA.forecast(events, period)
    sectors = []
    for s, row in fc.iterrows():
        ok = row["status"] == "ok"
        reasons = [code for code, hit in (
            ("insufficient_data", not ok),
            ("few_periods", ok and row["n_periods"] < RELIABLE_PERIODS),
            ("no_backtest", ok and not row["bt_origins"] > 0),
            ("not_better_than_naive", ok and not row["bt_mae"] < row["bt_naive_mae"]),
        ) if hit]
        sectors.append({
            **row.drop(["target_period", "intercept"]).to_dict(),
            "status": "ok" if ok else "insufficient_data",
            "sector": s,
            "fruits": n[s].sum(),
            "reliable": not reasons,
            "reasons": reasons,
            "history": props[s],
            "history_n": n[s],
        })
    return {
        "status": "ok",
        "n": total(events),
        "labels": FA.period_labels(props.index, period),
        "target_period": fc["target_period"].iloc[0],
        "min_periods": FA.MIN_PERIODS,
        "min_fruits": FA.MIN_FRUITS,
        "reliable_min_periods": RELIABLE_PERIODS,
        "sectors": sectors,
    }


def fruits(events, period):
    c = FA.fruit_counts(events)
    tie = len(c) > 1 and c["n"].iloc[0] == c["n"].iloc[1]
    return {
        "status": "ok",
        "n": int(c["n"].sum()),
        "items": [{"fruit": f, "n": n, "share": sh} for f, n, sh in zip(c.index, c["n"], c["share"])],
        "top": c.index[0] if c["n"].iloc[0] > 0 and not tie else None,
        "tie": tie,
    }


def whole_periods(events, period):
    p = events["timestamp"].dt.to_period("M" if period == "season" else FA.FREQ[period])
    lo, hi = p.min(), p.max()
    if events["timestamp"].min().normalize() > lo.start_time:
        lo += 1
    if events["timestamp"].max().normalize() < hi.end_time.normalize():
        hi -= 1
    if period == "season":
        while lo <= hi and FA.SEASONS[(lo - 1).month] == FA.SEASONS[lo.month]:
            lo += 1
        while lo <= hi and FA.SEASONS[(hi + 1).month] == FA.SEASONS[hi.month]:
            hi -= 1
    return events[(p >= lo) & (p <= hi)]


def growth(events, period):
    whole = whole_periods(events, period)
    if whole.empty:
        return {"status": "insufficient_data", "n": 0, "n_periods": 0, "excluded": total(events)}
    g = FA.growth(whole, period)
    out = {"status": "ok" if len(g) >= 2 else "insufficient_data", "n": total(whole), "excluded": total(events) - total(whole), "n_periods": len(g), "labels": FA.period_labels(g.index, period)}
    for k in ("good", "rotten"):
        out[k] = {"count": g[k], "prop": g[f"{k}_prop"], "count_growth": g[f"{k}_count_growth"], "prop_growth": g[f"{k}_prop_growth"]}
    return out


def recurring(events, period):
    out = {"status": "ok", "n": total(events), "seasons": list(dict.fromkeys(FA.SEASONS.values()))}
    for p in ("week", "month", "season"):
        whole = whole_periods(events, p)
        t = FA.recurring_growth(whole, p) if len(whole) else pd.DataFrame(columns=["good_median_growth", "rotten_median_growth", "good_n", "rotten_n"])
        out[p] = {
            "n": total(whole),
            "excluded": total(events) - total(whole),
            "buckets": [str(b) for b in t.index],
            "good": t["good_median_growth"],
            "rotten": t["rotten_median_growth"],
            "good_n": t["good_n"],
            "rotten_n": t["rotten_n"],
            "max_n": int(t["rotten_n"].max()) if len(t) else 0,
        }
    return out


def gaussian(events, period):
    props, _ = FA.sector_proportions(events, period)
    fit = FA.gaussian_fit(props)
    sectors = []
    for s, r in fit.iterrows():
        x = props[s].dropna().to_numpy()
        item = {"sector": s, **r.to_dict(), "reasons": [code for code, hit in (
            ("small_n", r["n"] < FA.MIN_GAUSS_N),
            ("no_variance", not r["std"] > 0),
            ("not_normal", r["shapiro_p"] < FA.ALPHA),
            ("outside_01", r["mass_outside_01"] > FA.MAX_OUTSIDE),
        ) if hit]}
        if len(x) >= 3 and r["std"] > 0:
            density, edges = np.histogram(x, bins="auto", density=True)
            xs = np.linspace(r["mean"] - 4 * r["std"], r["mean"] + 4 * r["std"], 81)
            (osm, osr), (slope, intercept, _) = st.probplot(x, dist="norm")
            item.update(
                hist={"edges": edges, "density": density},
                pdf={"x": xs, "y": st.norm.pdf(xs, r["mean"], r["std"])},
                qq={"theoretical": osm, "observed": osr, "slope": slope, "intercept": intercept},
            )
        sectors.append(item)
    return {"status": "ok", "n": total(events), "min_n": FA.MIN_GAUSS_N, "alpha": FA.ALPHA, "max_outside": FA.MAX_OUTSIDE, "sectors": sectors}


def overview(events, period):
    c = FA.counts(events, period)
    rotten = tally(events[~events["is_good"]], "deformity_type")
    fruit = tally(events, "fruit_type")
    w = weights(events)
    n, n_good = int(w.sum()), int(w[events["is_good"]].sum())
    by_sector = pd.DataFrame({"n": w, "bad": w.where(~events["is_good"], 0)}).groupby(events["sector"]).sum()
    return {
        "status": "ok",
        "n": n,
        "n_good": n_good,
        "n_rotten": n - n_good,
        "rotten_rate": (n - n_good) / n,
        "n_sectors": events["sector"].nunique(),
        "top_fruit": fruit.index[0] if len(fruit) and (len(fruit) == 1 or fruit.iloc[0] > fruit.iloc[1]) else None,
        "top_deformity": rotten.index[0] if len(rotten) and (len(rotten) == 1 or rotten.iloc[0] > rotten.iloc[1]) else None,
        "labels": FA.period_labels(c.index, period),
        "good": c["good"],
        "rotten": c["rotten"],
        "sectors": [{"sector": k, "n": int(r["n"]), "rotten_rate": float(r["bad"] / r["n"])} for k, r in by_sector.iterrows()],
    }


BUILDERS = {
    "deformity": deformity,
    "forecast": forecast,
    "fruits": fruits,
    "growth": growth,
    "recurring": recurring,
    "gaussian": gaussian,
    "overview": overview,
}
