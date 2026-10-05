import math

import numpy as np
import pandas as pd

LABELS = ("boa", "baixa_qualidade", "podre")
Z = 1.959964
RUN = 8


def wilson(k, n):
    if n <= 0:
        return [None, None]
    p = k / n
    centre = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return [max(0.0, centre - half), min(1.0, centre + half)]


def classify_rows(df):
    label = df["label"].where(~df["needs_review"], "revisar")
    return label.where(label.isin(LABELS + ("revisar",)), "revisar")


def windows(df, start, end, minutes):
    edges = pd.date_range(start, end, freq=f"{minutes}min")
    if len(edges) < 2:
        return pd.DataFrame(columns=["start", "n", *LABELS, "revisar"])
    cat = classify_rows(df) if len(df) else pd.Series(dtype=str)
    bins = pd.cut(df["timestamp"], edges, right=False, labels=edges[:-1]) if len(df) else pd.Series(dtype=object)
    table = pd.crosstab(bins, cat).reindex(index=edges[:-1], columns=[*LABELS, "revisar"], fill_value=0) if len(df) else pd.DataFrame(0, index=edges[:-1], columns=[*LABELS, "revisar"])
    table.index.name = "start"
    table = table.reset_index()
    table["n"] = table[[*LABELS, "revisar"]].sum(axis=1)
    return table


def p_chart(k, n, center=None, sigma=3.0):
    k, n = np.asarray(k, float), np.asarray(n, float)
    valid = n > 0
    p = np.where(valid, k / np.maximum(n, 1), np.nan)
    clean = lambda a: [None if a[i] is None or not np.isfinite(a[i]) else float(a[i]) for i in range(len(a))]
    if valid.sum() < 2:
        return {"center": None, "sigma_z": None, "p": clean(p), "ucl": [None] * len(n), "lcl": [None] * len(n), "alarms": []}
    if center is None:
        center = float(np.median(p[valid]))
    center = min(max(center, 1e-6), 1 - 1e-6)
    se = np.sqrt(center * (1 - center) / np.maximum(n, 1))
    z = (p[valid] - center) / se[valid]
    moving = np.abs(np.diff(z))
    sigma_z = max(float(np.median(moving)) / 0.954, 1.0) if len(moving) else 1.0
    ucl = np.where(valid, np.minimum(1, center + sigma * sigma_z * se), np.nan)
    lcl = np.where(valid, np.maximum(0, center - sigma * sigma_z * se), np.nan)
    alarms = []
    run = 0
    for i in range(len(n)):
        if not valid[i]:
            run = 0
            continue
        if p[i] > ucl[i]:
            alarms.append({"index": i, "rule": "acima_do_limite"})
        run = run + 1 if p[i] > center else 0
        if run == RUN:
            alarms.append({"index": i, "rule": "sequencia_acima_da_mediana"})
    return {"center": center, "sigma_z": sigma_z, "p": clean(p), "ucl": clean(ucl), "lcl": clean(lcl), "alarms": alarms}


def lot_verdict(k, n, max_share):
    lo, hi = wilson(k, n)
    if lo is None:
        return "sem_dados"
    if hi <= max_share:
        return "aprovado"
    if lo > max_share:
        return "reprovado"
    return "inconclusivo"


def summary(df, start, end, minutes=1, max_rotten=None, center=None):
    table = windows(df, start, end, minutes)
    complete = table[table["start"] + pd.Timedelta(minutes=minutes) <= end].reset_index(drop=True)
    total = int(complete["n"].sum())
    counts = {c: int(complete[c].sum()) for c in (*LABELS, "revisar")}
    decided = sum(counts[c] for c in LABELS)
    shares = {c: {"k": counts[c], "n": decided, "share": counts[c] / decided if decided else None, "ci95": wilson(counts[c], decided)} for c in LABELS}
    chart = p_chart(complete["podre"].to_numpy(), (complete["n"] - complete["revisar"]).to_numpy(), center)
    span = len(complete) * minutes
    lots = []
    if len(df) and "lot" in df:
        for lot, g in df[df["lot"].fillna("") != ""].groupby("lot"):
            cat = classify_rows(g)
            k = {c: int((cat == c).sum()) for c in (*LABELS, "revisar")}
            n = sum(k[c] for c in LABELS)
            lots.append({
                "lot": lot,
                "first": g["timestamp"].min().isoformat(),
                "last": g["timestamp"].max().isoformat(),
                "n": int(len(g)),
                "counts": k,
                "rotten": {"share": k["podre"] / n if n else None, "ci95": wilson(k["podre"], n)},
                "poor": {"share": k["baixa_qualidade"] / n if n else None, "ci95": wilson(k["baixa_qualidade"], n)},
                "verdict": lot_verdict(k["podre"], n, max_rotten) if max_rotten is not None else None,
            })
    return {
        "window_minutes": minutes,
        "windows": [{"start": r["start"].isoformat(), "n": int(r["n"]), **{c: int(r[c]) for c in (*LABELS, "revisar")}} for _, r in complete.iterrows()],
        "total": total,
        "counts": counts,
        "shares": shares,
        "throughput_per_min": total / span if span else None,
        "review_share": counts["revisar"] / total if total else None,
        "p_chart": chart,
        "lots": sorted(lots, key=lambda r: r["first"]),
        "max_rotten": max_rotten,
    }
