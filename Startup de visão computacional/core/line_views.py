import json
import shutil
import time
from datetime import timedelta

import pandas as pd
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import FileResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response

from belt import stats as belt_stats

from . import rollups, supervisor
from .cameras import camera, cameras, status
from .models import Event
from .stats import clean

WINDOWS = (1, 5, 15, 60)
STREAM_SECONDS = 600
STREAM_FPS = 15
LIVE_SECONDS = 600
LIVE_REFRESH = 5.0
HEALTH_FIELDS = ("online", "state", "age_s", "fps", "counted", "passages", "backlog_bytes", "db_busy", "dropped_frames", "reconnects", "process_ms", "frame_age_s")
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


def mjpeg(path):
    started, last, quiet = time.monotonic(), None, 0.0
    while time.monotonic() - started < STREAM_SECONDS and quiet < 10:
        try:
            stamp = path.stat().st_mtime_ns
            data = path.read_bytes() if stamp != last else b""
            last = stamp
        except OSError:
            data = b""
        if data:
            quiet = 0.0
            yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n"
        else:
            quiet += 1 / STREAM_FPS
        time.sleep(1 / STREAM_FPS)


@api_view(["GET"])
def camera_stream(request, slug):
    path = settings.RUN_DIR / slug / "frame.jpg"
    if camera(slug) is None or not path.exists():
        return error("no_frame", 404)
    response = StreamingHttpResponse(mjpeg(path), content_type="multipart/x-mixed-replace; boundary=frame")
    response["Cache-Control"] = "no-store"
    return response


def line_filters(q):
    cam = camera(q.get("camera", ""))
    try:
        minutes = int(q.get("minutes", 60))
        window = int(q.get("window", 1))
    except ValueError:
        return None, error("invalid_filter", 400)
    source = q.get("source", "real")
    if cam is None:
        return None, error("unknown_camera", 404)
    if minutes not in SPANS or window not in WINDOWS or window * 4 > minutes or source not in ("real", "demo", "all"):
        return None, error("invalid_filter", 400)
    return (cam, minutes, window, source), None


def line_body(cam, minutes, window, source):
    tz = timezone.get_current_timezone()
    end = timezone.localtime(timezone.now(), tz).replace(second=0, microsecond=0)
    start = end - timedelta(minutes=minutes)
    key = f"line:{cam['slug']}:{source}:{minutes}:{window}:{end.isoformat()}:{rollups.version()}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    naive_start, naive_end = start.replace(tzinfo=None), end.replace(tzinfo=None)
    max_rotten = cam.get("max_rotten_share")
    if rollups.usable(start):
        table, lots, hist, demo = rollups.line(cam["slug"], start, end, source, window, tz)
        body = belt_stats.report(table, [belt_stats.lot_row(lot["lot"], lot["counts"], lot["first"], lot["last"], max_rotten) for lot in lots], pd.Timestamp(naive_end), window, max_rotten)
    else:
        qs = Event.objects.filter(source="camera", camera=cam["slug"], timestamp__gte=start, timestamp__lt=end)
        if source != "all":
            qs = qs.filter(is_demo=source == "demo")
        rows = list(qs.values_list("timestamp", "label", "needs_review", "lot", "is_demo", "size_mm"))
        df = pd.DataFrame(rows, columns=["timestamp", "label", "needs_review", "lot", "is_demo", "size_mm"])
        if len(df):
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(tz).dt.tz_localize(None)
        body = belt_stats.summary(df, pd.Timestamp(naive_start), pd.Timestamp(naive_end), window, max_rotten)
        hist = rollups.size_hist(df["size_mm"]) if len(df) else {}
        demo = bool(df["is_demo"].any()) if len(df) else False
    body.update(camera=public(cam), source=source, demo=demo, minutes=minutes, start=naive_start.isoformat(), end=naive_end.isoformat(), size_mm=rollups.size_summary(hist))
    body = clean(body)
    cache.set(key, body, 120)
    return body


@api_view(["GET"])
def line_summary(request):
    filters, problem = line_filters(request.query_params)
    if problem is not None:
        return problem
    return Response({**line_body(*filters), "status": status(filters[0]["slug"])})


class EventStream(BaseRenderer):
    media_type = "text/event-stream"
    format = "sse"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data if isinstance(data, bytes) else json.dumps(data).encode()


def sse(event, data):
    return f"event: {event}{chr(10)}data: {json.dumps(data, ensure_ascii=False)}{chr(10)}{chr(10)}".encode()


def live_events(cam, minutes, window, source, seconds=LIVE_SECONDS, pause=1.0):
    started, sent, computed = time.monotonic(), None, 0.0
    while time.monotonic() - started < seconds:
        mark = (timezone.now().replace(second=0, microsecond=0), rollups.version())
        state = status(cam["slug"])
        now = time.monotonic()
        if sent is None or mark[0] != sent[0] or (mark != sent and now - computed >= LIVE_REFRESH):
            yield sse("summary", {**line_body(cam, minutes, window, source), "status": state})
            sent, computed = mark, now
        else:
            yield sse("status", state)
        time.sleep(pause)


@api_view(["GET"])
@renderer_classes([JSONRenderer, EventStream])
def line_live(request):
    filters, problem = line_filters(request.query_params)
    if problem is not None:
        return problem
    response = StreamingHttpResponse(live_events(*filters), content_type="text/event-stream")
    response["Cache-Control"] = "no-store"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        state = rollups.state()
        aggregates = {"in_sync": rollups.in_sync(), "mutations": state.mutations if state else 0, "synced": state.synced if state else 0, "horizon": state.horizon, "rebuilt": state.rebuilt, "triggers": len(rollups.triggers())}
        database = True
    except DatabaseError:
        aggregates, database = None, False
    cams = [{"slug": c["slug"], **{k: v for k, v in status(c["slug"]).items() if k in HEALTH_FIELDS}} for c in cameras()]
    watch = supervisor.status()
    late = watch["online"] and any(not c["online"] for c in cams)
    verdict = "down" if not database else "degraded" if late or not aggregates["in_sync"] else "ok"
    if not request.user.is_authenticated:
        return Response({"status": verdict}, status=200 if database else 503)
    return Response({
        "status": verdict,
        "database": database,
        "aggregates": aggregates,
        "cameras": cams,
        "supervisor": watch,
        "disk_free_mb": shutil.disk_usage(settings.BASE_DIR).free // (1024 * 1024),
    }, status=200 if database else 503)
