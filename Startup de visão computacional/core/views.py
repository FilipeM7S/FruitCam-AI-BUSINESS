import re
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.db.models import Count, Max, Q
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import exception_handler

import fruit_analytics as FA

from . import stats
from .inference import UploadRejected, get_model, run_model, save_upload
from .models import Event

SOURCES = ("real", "demo", "all")
SHARE_IMAGE = re.compile(r'(<meta (?:property|name)="(?:og|twitter):image" content=")(/[^"]*)')


class LoginThrottle(SimpleRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def error(code, status, **extra):
    return Response({"error": {"code": code, **extra}}, status=status)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    codes = exc.get_codes() if isinstance(exc, APIException) else "error"
    detail = str(getattr(exc, "detail", ""))
    code = codes if isinstance(codes, str) else "invalid"
    if detail.startswith("CSRF Failed"):
        code = "csrf_failed"
    body = {"code": code, "detail": detail}
    if getattr(exc, "wait", None) is not None:
        body["wait_seconds"] = int(exc.wait) + 1
    response.data = {"error": body}
    return response


def csrf_failure(request, reason=""):
    return JsonResponse({"error": {"code": "csrf_failed", "detail": reason}}, status=403)


def not_found(request, exception=None):
    return JsonResponse({"error": {"code": "not_found"}}, status=404)


def server_error(request):
    return JsonResponse({"error": {"code": "server_error"}}, status=500)


def api_not_found(request):
    return not_found(request)


def spa(request):
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return JsonResponse({"error": {"code": "frontend_not_built"}}, status=503)
    origin = request.build_absolute_uri("/").rstrip("/")
    return HttpResponse(SHARE_IMAGE.sub(lambda m: m.group(1) + origin + m.group(2), index.read_text(encoding="utf-8")))


def user_json(user):
    return {"username": user.username}


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    return Response({"csrf_token": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login_view(request):
    SessionAuthentication().enforce_csrf(request)
    data = request.data if hasattr(request.data, "get") else {}
    user = authenticate(request, username=str(data.get("username", "")), password=str(data.get("password", "")))
    if user is None:
        return error("invalid_credentials", 400)
    login(request, user)
    return Response({"user": user_json(user), "csrf_token": get_token(request)})


@api_view(["POST"])
def logout_view(request):
    logout(request)
    return Response({"csrf_token": get_token(request)})


@api_view(["GET"])
def me(request):
    return Response({"user": user_json(request.user)})


def event_json(e):
    return {
        "id": e.id,
        "timestamp": timezone.localtime(e.timestamp).isoformat(),
        "sector": e.sector,
        "fruit_type": e.fruit_type,
        "is_good": e.is_good,
        "deformity_type": e.deformity_type,
        "confidence": e.confidence,
        "user": e.user.username if e.user else None,
        "is_demo": e.is_demo,
        "label": e.label,
        "needs_review": e.needs_review,
    }


@api_view(["POST"])
def analyze(request):
    sector = " ".join(str(request.data.get("sector", "")).split()).lower()
    fruit = str(request.data.get("fruit_type", "")).strip()
    image = request.FILES.get("image")
    if image is None:
        return error("image_required", 400)
    if not sector or len(sector) > 50:
        return error("invalid_sector", 400)
    if fruit not in FA.FRUIT_TYPES:
        return error("invalid_fruit_type", 400)
    try:
        name, img = save_upload(image)
    except UploadRejected as exc:
        code = str(exc)
        return error(code, 413 if code == "file_too_large" else 400, max_mb=settings.MAX_UPLOAD_BYTES // (1024 * 1024))
    result = run_model(settings.UPLOAD_DIR / name, img)
    event = Event.objects.create(
        sector=sector,
        fruit_type=fruit,
        is_good=result["is_good"],
        deformity_type=result["deformity_type"],
        confidence=result["confidence"],
        user=request.user,
        image=name,
        source="foto",
        label=result["label"],
        needs_review=result["needs_review"],
        decided_by="modelo",
        model_version=result["model_version"],
    )
    return Response({
        "event": event_json(event),
        "detections": [{k: result[k] for k in ("box", "label", "is_good", "deformity_type", "confidence", "probs", "needs_review")}],
        "model_version": result["model_version"],
        "image": {"width": img.width, "height": img.height},
        "inference_ms": round(result["inference_ms"], 1),
        "classes": get_model()[1],
    }, status=201)


def parse_filters(q):
    period = q.get("period", "week")
    source = q.get("source", "real")
    if period not in FA.FREQ or source not in SOURCES:
        raise ValueError
    tz = timezone.get_current_timezone()
    start = q.get("start") or None
    end = q.get("end") or None
    start = datetime.combine(date.fromisoformat(start), time.min, tz) if start else None
    end = datetime.combine(date.fromisoformat(end) + timedelta(days=1), time.min, tz) if end else None
    return period, source, q.get("sector") or None, start, end


@api_view(["GET"])
def sectors(request):
    source = request.query_params.get("source", "real")
    if source not in SOURCES:
        return error("invalid_filter", 400)
    qs = Event.objects.all() if source == "all" else Event.objects.filter(is_demo=source == "demo")
    return Response({"sectors": sorted(qs.values_list("sector", flat=True).distinct())})


@api_view(["GET"])
def stats_view(request, name):
    if name not in stats.BUILDERS:
        return error("not_found", 404)
    try:
        period, source, sector, start, end = parse_filters(request.query_params)
    except ValueError:
        return error("invalid_filter", 400)
    version = Event.objects.aggregate(n=Count("id"), last=Max("id"), pending=Count("id", filter=Q(needs_review=True)))
    key = f"stats:{name}:{request.query_params.urlencode()}:{version['n']}:{version['last']}:{version['pending']}"
    body = cache.get(key)
    if body is None:
        events, has_demo = stats.load_events(source, sector, start, end)
        body = {"status": "no_data", "n": 0} if events.empty else stats.BUILDERS[name](events, period)
        body.update(period=period, source=source, sector=sector, demo=has_demo)
        body = stats.clean(body)
        cache.set(key, body, 300)
    return Response(body)
