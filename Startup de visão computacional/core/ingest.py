from datetime import datetime

from django.db import transaction

from . import rollups
from .models import Event

GOOD = ("boa", "nao_podre")
DEFECTS = ("baixa_qualidade", "podre")
LOOKUP = 400


def known(uids):
    found = set()
    for i in range(0, len(uids), LOOKUP):
        found.update(Event.objects.filter(uid__in=uids[i:i + LOOKUP]).values_list("uid", flat=True))
    return found


def store(events):
    events = list(events)
    if not events:
        return []
    with transaction.atomic():
        seen = known([e.uid for e in events if e.uid])
        fresh = []
        for e in events:
            if e.uid:
                if e.uid in seen:
                    continue
                seen.add(e.uid)
            fresh.append(e)
        if fresh:
            healthy = rollups.in_sync()
            Event.objects.bulk_create(fresh, batch_size=2000)
            if healthy:
                rollups.apply(fresh)
                rollups.credit(len(fresh))
    return fresh


def record(event):
    return store([event])[0]


def passage_record(cam, passage, uid, timestamp, lot, is_demo, version):
    label = passage["label"]
    number = lambda value: None if value is None else float(value)
    return {
        "uid": uid,
        "timestamp": timestamp.isoformat(),
        "sector": cam["line"],
        "fruit_type": cam["fruit_type"],
        "is_good": label in GOOD,
        "deformity_type": label if label in DEFECTS else None,
        "confidence": number(passage["confidence"]),
        "is_demo": bool(is_demo),
        "source": "camera",
        "camera": cam["slug"],
        "lot": lot or "",
        "track_id": None if passage["track_id"] is None else int(passage["track_id"]),
        "label": label,
        "size_mm": number(passage["size_mm"]),
        "needs_review": bool(passage["needs_review"] or label not in GOOD + DEFECTS),
        "decided_by": passage["decided_by"],
        "model_version": version,
    }


def event_from(record):
    return Event(**{**record, "timestamp": datetime.fromisoformat(record["timestamp"])})
