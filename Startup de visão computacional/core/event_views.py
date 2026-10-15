import io
import re
from datetime import date, datetime, time, timedelta

import numpy as np
from django.conf import settings
from django.db import connection
from django.db.models import Count, Max, Min, Q
from django.http import HttpResponse
from django.utils import timezone
from PIL import Image
from rest_framework.decorators import api_view
from rest_framework.response import Response

from analytics import fruit_analytics as FA

from .inference import get_model
from .models import Event

SOURCES = ("real", "demo", "all")
KINDS = ("foto", "camera")
LABELS = ("boa", "baixa_qualidade", "podre")
STEPS = 100
EDGES = np.array([j / STEPS for j in range(STEPS + 1)])
TEXT = ("sector", "camera", "lot")
COLUMNS = ("id", "timestamp", "label", "needs_review", "confidence", "size_mm")
IMAGE_NAME = re.compile(r"[0-9a-f]{32}\.png")
MAX_PAGE = 500
MAX_LOT = 20000


def error(code, status):
    return Response({"error": {"code": code}}, status=status)


def day(value, plus=0):
    return datetime.combine(date.fromisoformat(value) + timedelta(days=plus), time.min, timezone.get_current_timezone())


def moment(value):
    dt = datetime.fromisoformat(value)
    return timezone.make_aware(dt, timezone.get_current_timezone()) if timezone.is_naive(dt) else dt


def filtered(q, user):
    source = q.get("source", "real")
    if source not in SOURCES:
        raise ValueError
    qs = Event.objects.all() if source == "all" else Event.objects.filter(is_demo=source == "demo")
    for key in TEXT:
        value = q.get(key)
        if value:
            if len(value) > 50:
                raise ValueError
            qs = qs.filter(**{key: value})
    fruit, kind, label, review = q.get("fruit_type"), q.get("kind"), q.get("label"), q.get("review")
    if fruit:
        if fruit not in FA.FRUIT_TYPES:
            raise ValueError
        qs = qs.filter(fruit_type=fruit)
    if kind:
        if kind not in KINDS:
            raise ValueError
        qs = qs.filter(source=kind)
    if label:
        if label not in LABELS:
            raise ValueError
        qs = qs.filter(label=label)
    if review:
        if review not in ("yes", "no"):
            raise ValueError
        qs = qs.filter(needs_review=review == "yes")
    if q.get("mine") == "1":
        qs = qs.filter(user=user)
    for key, op in (("since", "gte"), ("until", "lt")):
        if q.get(key):
            qs = qs.filter(**{f"timestamp__{op}": moment(q[key])})
    if q.get("start"):
        qs = qs.filter(timestamp__gte=day(q["start"]))
    if q.get("end"):
        qs = qs.filter(timestamp__lt=day(q["end"], 1))
    return qs


def visible_image(e, user):
    return bool(e.image) and e.source == "foto" and (e.user_id == user.id or user.is_staff)


def row(e, user):
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
        "source": e.source,
        "camera": e.camera,
        "lot": e.lot,
        "track_id": e.track_id,
        "label": e.label,
        "size_mm": e.size_mm,
        "needs_review": e.needs_review,
        "decided_by": e.decided_by,
        "model_version": e.model_version,
        "image": visible_image(e, user),
    }


def columns(qs):
    data = {k: [] for k in COLUMNS}
    for values in qs.values_list(*COLUMNS):
        for k, v in zip(COLUMNS, values):
            data[k].append(round(v.timestamp() * 1000) if k == "timestamp" else v)
    return data


@api_view(["GET"])
def events(request):
    q = request.query_params
    try:
        qs = filtered(q, request.user)
        page = int(q.get("page", 1))
        size = int(q.get("size", 50))
        order = q.get("order", "desc")
        shape = q.get("shape", "rows")
        if page < 1 or not 1 <= size <= (MAX_LOT if q.get("lot") else MAX_PAGE) or order not in ("asc", "desc") or shape not in ("rows", "columns", "lots"):
            raise ValueError
    except ValueError:
        return error("invalid_filter", 400)
    if shape == "lots":
        lots = qs.exclude(lot="").values("camera", "lot").annotate(n=Count("id"), first=Min("timestamp"), last=Max("timestamp"), demo=Max("is_demo")).order_by("-last")[:200]
        return Response({"lots": [{**r, "first": timezone.localtime(r["first"]).isoformat(), "last": timezone.localtime(r["last"]).isoformat(), "demo": bool(r["demo"])} for r in lots]})
    qs = qs.order_by(*(("timestamp", "id") if order == "asc" else ("-timestamp", "-id")))
    total = qs.count()
    part = qs[(page - 1) * size : page * size]
    body = {"total": total, "page": page, "size": size, "order": order, "demo": qs.filter(is_demo=True).exists()}
    if shape == "columns":
        body["columns"] = columns(part)
    else:
        body["events"] = [row(e, request.user) for e in part.select_related("user")]
    return Response(body)


@api_view(["GET"])
def event_detail(request, pk):
    e = Event.objects.select_related("user").filter(pk=pk).first()
    if e is None:
        return error("not_found", 404)
    return Response({"event": row(e, request.user)})


@api_view(["GET"])
def event_image(request, pk):
    e = Event.objects.filter(pk=pk).first()
    path = settings.UPLOAD_DIR / e.image if e and IMAGE_NAME.fullmatch(e.image or "") else None
    if e is None or not visible_image(e, request.user) or path is None or not path.exists():
        return error("not_found", 404)
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((320, 320))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
    response = HttpResponse(buf.getvalue(), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    return response


def histograms(qs):
    sql, params = qs.exclude(confidence__isnull=True).values_list("label", "confidence", "needs_review").query.sql_with_params()
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    out = {}
    if not rows:
        return out
    labels = np.array([r[0] or "sem_classe" for r in rows])
    conf = np.array([r[1] for r in rows], float)
    review = np.array([bool(r[2]) for r in rows])
    bins = np.clip(np.searchsorted(EDGES, conf, side="right") - 1, 0, STEPS)
    for label in np.unique(labels):
        m = labels == label
        out[str(label)] = {"bins": np.bincount(bins[m], minlength=STEPS + 1).tolist(), "n": int(m.sum()), "stored_review": int(review[m].sum())}
    return out


@api_view(["GET"])
def thresholds(request):
    try:
        qs = filtered(request.query_params, request.user)
    except ValueError:
        return error("invalid_filter", 400)
    counts = qs.aggregate(total=Count("id"), missing=Count("id", filter=Q(confidence__isnull=True)), demo=Count("id", filter=Q(is_demo=True)))
    classifier = get_model()[0]
    return Response({
        "steps": STEPS,
        "classes": histograms(qs),
        "total": counts["total"],
        "no_confidence": counts["missing"],
        "demo": counts["demo"] > 0,
        "model": {"version": classifier.version, "reject_below": classifier.reject_below},
    })
