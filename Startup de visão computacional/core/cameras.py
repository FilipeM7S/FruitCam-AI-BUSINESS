import json
import os
import time

from django.conf import settings


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
    data = None
    for attempt in range(5):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            break
        except FileNotFoundError:
            break
        except (OSError, ValueError):
            time.sleep(0.01 * (attempt + 1))
    if data is None:
        return {"online": False}
    age = time.time() - data.get("updated", 0)
    return {**data, "age_s": round(age, 1), "online": age <= settings.CAMERA_ONLINE_SECONDS}
