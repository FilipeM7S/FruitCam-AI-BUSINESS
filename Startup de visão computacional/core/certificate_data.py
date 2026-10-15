import hashlib
import json
import math
from datetime import timedelta

import numpy as np
import pandas as pd
from django.conf import settings
from django.utils import timezone

from analytics import fruit_analytics as FA
from belt import stats as belt_stats

from . import stats
from .cameras import cameras
from .models import Event

LINE_WINDOWS = (1, 5, 15, 60, 240, 1440, 10080)
MAX_LINE_WINDOWS = 150
EVAL_KEYS = ("model", "data", "test", "belt")
SIZE_EDGES = np.arange(20, 86, 2)


def local(dt):
    return pd.Timestamp(timezone.localtime(dt).replace(tzinfo=None))


def line_window(minutes):
    return next((w for w in LINE_WINDOWS if minutes / w <= MAX_LINE_WINDOWS), LINE_WINDOWS[-1])


def align(ts, window):
    if window >= 1440:
        day = ts.normalize()
        return day - pd.Timedelta(days=day.weekday()) if window == 10080 else day
    return ts.floor(f"{window}min")


def camera_section(cam, source, start, end):
    info = {k: cam.get(k) for k in ("slug", "name", "line", "fruit_type", "max_rotten_share")}
    qs = Event.objects.filter(source="camera", camera=cam["slug"])
    if source != "all":
        qs = qs.filter(is_demo=source == "demo")
    if start:
        qs = qs.filter(timestamp__gte=start)
    if end:
        qs = qs.filter(timestamp__lt=end)
    df = stats.rows(qs, ["timestamp", "label", "needs_review", "lot", "is_demo", "size_mm"])
    if df.empty:
        return {"camera": info, "status": "no_data", "n": 0}
    df["needs_review"] = df["needs_review"].astype(bool)
    df["is_demo"] = df["is_demo"].astype(bool)
    lo = local(start) if start else df["timestamp"].min()
    hi = local(end) if end else df["timestamp"].max() + pd.Timedelta(minutes=1)
    window = line_window((hi - lo) / pd.Timedelta(minutes=1))
    if not start:
        lo = align(lo, window)
    if not end:
        hi = lo + pd.Timedelta(minutes=window) * math.ceil((hi - lo) / pd.Timedelta(minutes=window))
    body = belt_stats.summary(df, lo, hi, window, cam.get("max_rotten_share"))
    sizes = df["size_mm"].dropna()
    classes = belt_stats.classify_rows(df)
    body.update(
        size_hist={"edges": SIZE_EDGES, "counts": {c: np.histogram(df.loc[classes == c, "size_mm"].dropna(), bins=SIZE_EDGES)[0] for c in belt_stats.LABELS}},
        camera=info,
        status="ok",
        n=len(df),
        demo=bool(df["is_demo"].any()),
        start=lo.isoformat(),
        end=hi.isoformat(),
        size_mm={"median": float(sizes.median()), "p10": float(sizes.quantile(0.1)), "p90": float(sizes.quantile(0.9)), "n": int(len(sizes))} if len(sizes) else None,
    )
    return body


def model_eval():
    path = settings.BASE_DIR / "frontend" / "src" / "figures.json"
    try:
        ev = json.loads(path.read_text(encoding="utf-8"))["modelEval"]
    except (OSError, ValueError, KeyError):
        return None
    return {**{k: ev.get(k) for k in EVAL_KEYS}, "configured": settings.MODEL_PATH.name}


def coverage(events, period):
    if events.empty:
        return None
    p = events["timestamp"].dt.to_period(FA.FREQ[period])
    full = pd.period_range(p.min(), p.max(), freq=FA.FREQ[period])
    t = events.groupby([p, events["sector"]]).size().unstack(fill_value=0).reindex(full, fill_value=0)
    return {"labels": FA.period_labels(full, period), "sectors": list(t.columns), "counts": t.T.to_numpy()}


def fingerprint(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def collect(period, source, sector, start, end):
    events, has_demo = stats.load_events(source, sector, start, end)
    dashboard = {name: {"status": "no_data", "n": 0} if events.empty else build(events, period) for name, build in stats.BUILDERS.items()}
    all_cams = cameras()
    line = [camera_section(c, source, start, end) for c in all_cams if not sector or c["line"] == sector]
    qs = stats.scope(source, sector, start, end)
    scope = {
        "period": period,
        "source": source,
        "sector": sector,
        "start": timezone.localtime(start).date().isoformat() if start else None,
        "end": (timezone.localtime(end) - timedelta(days=1)).date().isoformat() if end else None,
        "first": events["timestamp"].min().isoformat() if len(events) else None,
        "last": events["timestamp"].max().isoformat() if len(events) else None,
        "n": len(events),
        "pending": qs.filter(needs_review=True).count(),
        "cameras_total": len(all_cams),
        "model_versions": sorted(set(qs.values_list("model_version", flat=True).distinct())),
        "time_zone": settings.TIME_ZONE,
        "demo": has_demo or any(c.get("demo") for c in line),
    }
    body = stats.clean({"scope": scope, "dashboard": dashboard, "line": line, "model": model_eval(), "extra": {"coverage": coverage(events, period)}})
    body["fingerprint"] = fingerprint(body)
    return body


def has_data(body):
    return body["scope"]["n"] > 0 or any(c["status"] == "ok" for c in body["line"])
