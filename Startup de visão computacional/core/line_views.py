from datetime import timedelta

import pandas as pd
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Max, Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from belt import stats as belt_stats

from .cameras import camera, cameras, status
from .models import Event
from .stats import clean

WINDOWS = (1, 5, 15, 60)
SPANS = (30, 60, 240, 480, 1440)


def error(code, http):
    return Response({"error": {"code": code}}, status=http)


def public(cam):
    return {k: cam.get(k) for k in ("slug", "name", "line", "fruit_type", "max_rotten_share", "min_size_mm")}


@api_view(["GET"])
def camera_list(request):
    return Response({"cameras": [{**public(c), "status": status(c["slug"])} for c in cameras()]})


@api_view(["GET"])
def camera_frame(request, slug):
    path = settings.RUN_DIR / slug / "frame.jpg"
    if camera(slug) is None or not path.exists():
        return error("no_frame", 404)
    response = FileResponse(path.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "no-store"
    return response


@api_view(["GET"])
def line_summary(request):
    q = request.query_params
    cam = camera(q.get("camera", ""))
    try:
        minutes = int(q.get("minutes", 60))
        window = int(q.get("window", 1))
    except ValueError:
        return error("invalid_filter", 400)
    source = q.get("source", "real")
    if cam is None:
        return error("unknown_camera", 404)
    if minutes not in SPANS or window not in WINDOWS or window * 4 > minutes or source not in ("real", "demo", "all"):
        return error("invalid_filter", 400)
    tz = timezone.get_current_timezone()
    end = timezone.localtime(timezone.now(), tz).replace(second=0, microsecond=0)
    start = end - timedelta(minutes=minutes)
    qs = Event.objects.filter(source="camera", camera=cam["slug"], timestamp__gte=start, timestamp__lt=end)
    if source != "all":
        qs = qs.filter(is_demo=source == "demo")
    version = qs.aggregate(n=Count("id"), last=Max("id"), pending=Count("id", filter=Q(needs_review=True)))
    key = f"line:{cam['slug']}:{source}:{minutes}:{window}:{end.isoformat()}:{version['n']}:{version['last']}:{version['pending']}"
    cached = cache.get(key)
    if cached is not None:
        return Response({**cached, "status": status(cam["slug"])})
    rows = list(qs.values_list("timestamp", "label", "needs_review", "lot", "is_demo", "size_mm"))
    df = pd.DataFrame(rows, columns=["timestamp", "label", "needs_review", "lot", "is_demo", "size_mm"])
    if len(df):
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(tz).dt.tz_localize(None)
    naive_start, naive_end = start.replace(tzinfo=None), end.replace(tzinfo=None)
    body = belt_stats.summary(df, pd.Timestamp(naive_start), pd.Timestamp(naive_end), window, cam.get("max_rotten_share"))
    sizes = df["size_mm"].dropna() if len(df) else pd.Series(dtype=float)
    body.update(
        camera=public(cam),
        status=status(cam["slug"]),
        source=source,
        demo=bool(df["is_demo"].any()) if len(df) else False,
        minutes=minutes,
        start=naive_start.isoformat(),
        end=naive_end.isoformat(),
        size_mm={"median": float(sizes.median()), "p10": float(sizes.quantile(0.1)), "p90": float(sizes.quantile(0.9)), "n": int(len(sizes))} if len(sizes) else None,
    )
    body = clean(body)
    cache.set(key, body, 120)
    return Response(body)
