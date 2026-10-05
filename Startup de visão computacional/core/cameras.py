import json
import os
import time

from django.conf import settings

from .models import Event

GOOD = ("boa", "nao_podre")
DEFECTS = ("baixa_qualidade", "podre")


def cameras():
    return json.loads(settings.CAMERAS_FILE.read_text(encoding="utf-8"))["cameras"]


def camera(slug):
    return next((c for c in cameras() if c["slug"] == slug), None)


def run_dir(slug):
    path = settings.RUN_DIR / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_atomic(path, data, attempts=5):
    tmp = path.with_name(path.name + ".tmp")
    for i in range(attempts):
        try:
            tmp.write_bytes(data)
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(0.02 * (i + 1))
    return False


def write_status(slug, **fields):
    write_atomic(run_dir(slug) / "status.json", json.dumps({**fields, "updated": time.time()}).encode())


def status(slug):
    path = settings.RUN_DIR / slug / "status.json"
    if not path.exists():
        return {"online": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"online": False}
    age = time.time() - data.get("updated", 0)
    return {**data, "age_s": round(age, 1), "online": age <= settings.CAMERA_ONLINE_SECONDS}


def passage_event(cam, passage, timestamp, lot, is_demo, version):
    label = passage["label"]
    return Event(
        timestamp=timestamp,
        sector=cam["line"],
        fruit_type=cam["fruit_type"],
        is_good=label in GOOD,
        deformity_type=label if label in DEFECTS else None,
        confidence=passage["confidence"],
        is_demo=is_demo,
        source="camera",
        camera=cam["slug"],
        lot=lot or "",
        track_id=passage["track_id"],
        label=label,
        size_mm=passage["size_mm"],
        needs_review=passage["needs_review"] or label not in GOOD + DEFECTS,
        decided_by=passage["decided_by"],
        model_version=version,
    )
