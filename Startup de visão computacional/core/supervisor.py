import json
import subprocess
import sys
import time

from django.conf import settings

from .cameras import run_dir, write_atomic

BACKOFF = (1.0, 60.0)
HEALTHY_SECONDS = 60.0
STOP_SECONDS = 40.0


def spawn(slug):
    return subprocess.Popen([sys.executable, str(settings.BASE_DIR / "manage.py"), "run_camera", slug])


def stop_file():
    settings.RUN_DIR.mkdir(parents=True, exist_ok=True)
    return settings.RUN_DIR / "supervisor.stop"


def status():
    path = settings.RUN_DIR / "supervisor.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"online": False}
    age = time.time() - data.get("updated", 0)
    return {**data, "age_s": round(age, 1), "online": age <= 5 and data.get("state") == "running"}


class Supervisor:
    def __init__(self, slugs, spawn=spawn, clock=time.monotonic, sleep=time.sleep, log=print):
        self.spawn = spawn
        self.clock = clock
        self.sleep = sleep
        self.log = log
        self.state = "running"
        self.children = {slug: {"process": None, "restarts": 0, "delay": BACKOFF[0], "started": None, "next": 0.0, "exit": None} for slug in slugs}

    def tick(self):
        now = self.clock()
        for slug, child in self.children.items():
            process = child["process"]
            if process is not None:
                code = process.poll()
                if code is None:
                    if now - child["started"] >= HEALTHY_SECONDS:
                        child["delay"] = BACKOFF[0]
                    continue
                child.update(process=None, exit=code, next=now + child["delay"])
                self.log(f"{slug}: processo terminou com código {code}; nova tentativa em {child['delay']:g} s")
                child["delay"] = min(child["delay"] * 2, BACKOFF[1])
            if now >= child["next"]:
                if child["exit"] is not None:
                    child["restarts"] += 1
                child.update(process=self.spawn(slug), started=now)
                self.log(f"{slug}: processo iniciado (pid {child['process'].pid})")
        self.publish()

    def publish(self):
        body = {
            "state": self.state,
            "updated": time.time(),
            "cameras": {slug: {"pid": c["process"].pid if c["process"] is not None else None, "running": c["process"] is not None, "restarts": c["restarts"], "last_exit": c["exit"]} for slug, c in self.children.items()},
        }
        settings.RUN_DIR.mkdir(parents=True, exist_ok=True)
        write_atomic(settings.RUN_DIR / "supervisor.json", json.dumps(body).encode())

    def run(self, should_stop, interval=1.0):
        while not should_stop():
            self.tick()
            self.sleep(interval)

    def stop(self, seconds=STOP_SECONDS):
        self.state = "stopping"
        alive = {slug: c["process"] for slug, c in self.children.items() if c["process"] is not None}
        for slug in alive:
            (run_dir(slug) / "stop").write_text("stop", encoding="ascii")
        deadline = self.clock() + seconds
        while any(p.poll() is None for p in alive.values()) and self.clock() < deadline:
            self.sleep(0.2)
        forced = []
        for slug, process in alive.items():
            if process.poll() is None:
                process.terminate()
                forced.append(slug)
            stop = run_dir(slug) / "stop"
            if stop.exists():
                stop.unlink()
        for child in self.children.values():
            if child["process"] is not None:
                child.update(exit=child["process"].poll(), process=None)
        self.state = "stopped"
        self.publish()
        return forced
