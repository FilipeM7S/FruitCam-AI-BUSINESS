import os
import signal
import threading
import time
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import cv2
from django.conf import settings
from django.db import DatabaseError, OperationalError, connection
from django.utils import timezone

from belt.capture import LatestFrame, is_live
from belt.classify import CropClassifier, ModelDecider, TruthDecider
from belt.pipeline import BeltPipeline
from belt.simulate import SimulatedBelt, crop_pool
from belt.source import CameraSource
from belt.spool import Spool

from . import ingest, rollups
from .cameras import run_dir, write_atomic, write_status

HEAL_SECONDS = 300.0
DRAIN_SECONDS = 30.0


class ServiceError(Exception):
    pass


class Writer:
    def __init__(self, spool, heal_every=HEAL_SECONDS):
        self.spool = spool
        self.heal_every = heal_every
        self.stored = 0
        self.duplicates = 0
        self.busy = 0
        self.error = ""
        self.healed = time.monotonic()
        self.wake = threading.Event()
        self.halt = threading.Event()
        self.deadline = None
        self.thread = None

    def step(self, limit=500):
        records, offset = self.spool.pending(limit)
        if offset == self.spool.offset:
            return 0
        try:
            fresh = ingest.store([ingest.event_from(r) for r in records])
        except OperationalError as exc:
            self.busy += 1
            self.error = str(exc)
            return -1
        self.spool.commit(offset)
        self.stored += len(fresh)
        self.duplicates += len(records) - len(fresh)
        self.error = ""
        return len(records)

    def heal(self):
        if time.monotonic() - self.healed < self.heal_every:
            return
        self.healed = time.monotonic()
        try:
            rollups.ensure()
        except DatabaseError as exc:
            self.error = str(exc)

    def drain(self, seconds=DRAIN_SECONDS):
        deadline, delay = time.monotonic() + seconds, 0.1
        while self.spool.backlog_bytes():
            done = self.step()
            if done == 0 or (done < 0 and time.monotonic() >= deadline):
                break
            if done < 0:
                time.sleep(delay)
                delay = min(delay * 2, 2.0)
        return self.spool.backlog_bytes() == 0

    def loop(self):
        delay = 0.0
        try:
            while True:
                done = self.step()
                delay = min(max(delay * 2, 0.2), 5.0) if done < 0 else 0.0
                if done > 0:
                    continue
                if self.halt.is_set() and (done == 0 or time.monotonic() >= self.deadline):
                    break
                if done == 0:
                    self.heal()
                self.wake.wait(delay or 0.25)
                self.wake.clear()
        finally:
            connection.close()

    def start(self):
        self.thread = threading.Thread(target=self.loop, name="fruitcam-writer", daemon=True)
        self.thread.start()

    def finish(self, seconds=DRAIN_SECONDS):
        self.deadline = time.monotonic() + seconds
        self.halt.set()
        self.wake.set()
        if self.thread is not None:
            self.thread.join(seconds + 25)
        return self.spool.backlog_bytes() == 0


class LineService:
    def __init__(self, cam, source=None, lot="", seconds=None, decider="auto", fast=False, snapshot_every=1 / 15, threaded=None, opener=None):
        self.cam = cam
        self.spec = source or cam["source"]
        self.lot = lot or ""
        self.seconds = seconds
        self.fast = fast
        self.snapshot_every = snapshot_every
        self.simulated = self.spec == "sim"
        if decider == "truth" and not self.simulated:
            raise ServiceError("--decider truth only exists for the simulator")
        self.use_truth = self.simulated and decider in ("auto", "truth")
        self.live = not self.simulated and is_live(self.spec)
        self.threaded = (not fast and not connection.in_atomic_block) if threaded is None else threaded
        self.opener = opener
        self.halt = threading.Event()
        self.reason = ""
        self.out = run_dir(cam["slug"])
        self.boot = int(time.time() * 1000)
        self.counted = 0
        self.process_ms = 0.0
        self.t = 0.0
        self.state = "starting"
        self.belt = self.stream = self.frames = self.pipe = self.spool = self.writer = None
        self.version = ""
        self.recovered = 0

    def open(self):
        cam = self.cam
        if self.simulated:
            sim = dict(cam.get("sim", {}))
            folder = sim.pop("crops", None)
            crops = crop_pool(settings.BASE_DIR / folder) if folder else None
            self.belt = SimulatedBelt(px_per_mm=cam["px_per_mm"], crops=crops, **sim)
            width, self.kind = self.belt.width, "simulação"
        elif self.live:
            self.frames = LatestFrame(self.spec, **({"opener": self.opener} if self.opener else {})).start()
            width, self.kind = None, "câmera"
        else:
            self.stream = CameraSource(self.spec)
            width, self.kind = None, "câmera"
        if self.use_truth:
            self.version = "simulacao"
            decide = TruthDecider(self.belt)
            stamp = "SIMULAÇÃO · cajus de fotos reais · rótulos do conjunto" if self.belt.crops else "SIMULAÇÃO · rótulos da simulação"
        else:
            classifier = CropClassifier(settings.MODEL_PATH)
            self.version = classifier.version
            decide = ModelDecider(classifier, cam.get("min_size_mm"))
            stamp = "SIMULAÇÃO · modelo em frutas sintéticas" if self.simulated else None
        first = self.read()
        while first is None and self.live and not self.stop_requested():
            self.state = self.frames.state
            self.publish()
            first = self.read()
        if first is None:
            raise ServiceError(f"no frames from {self.spec!r}")
        self.pipe = BeltPipeline(decide, cam["px_per_mm"], width or first[1].shape[1], cam.get("count_line", 0.62), cam.get("direction", 1), tuple(cam["belt_rows"]) if cam.get("belt_rows") else None, camera=cam["slug"], stamp=stamp)
        return first

    def read(self, timeout=1.0):
        if self.simulated:
            t, frame = self.belt.read()
            return None if frame is None else (t, frame, None)
        if self.live:
            return self.frames.read(timeout)
        t, frame = self.stream.read()
        return None if frame is None else (t, frame, None)

    def stop(self, reason="pedido de parada"):
        self.reason = self.reason or reason
        self.halt.set()

    def stop_requested(self):
        return self.halt.is_set() or (self.out / "stop").exists()

    def publish(self, state=None):
        grab = self.frames
        write_status(
            self.cam["slug"],
            source=self.kind,
            decider="simulação" if self.use_truth else "modelo",
            model_version=self.version,
            lot=self.lot,
            fps=round(self.pipe.fps(), 1) if self.pipe else 0.0,
            frames=self.pipe.frames if self.pipe else 0,
            passages=self.writer.stored if self.writer else 0,
            counted=self.counted,
            backlog_bytes=self.spool.backlog_bytes() if self.spool else 0,
            db_busy=self.writer.busy if self.writer else 0,
            stream_seconds=round(self.t, 1),
            real_crops=bool(self.belt is not None and self.belt.crops),
            state=state or self.state,
            process_ms=round(self.process_ms, 1),
            dropped_frames=grab.dropped if grab else 0,
            reconnects=grab.reconnects if grab else 0,
            frame_age_s=round(grab.age(), 2) if grab and grab.age() is not None else None,
            pid=os.getpid(),
            started=self.boot / 1000,
        )

    def install_signals(self):
        previous = {}
        if threading.current_thread() is not threading.main_thread():
            return previous
        for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            number = getattr(signal, name, None)
            if number is None:
                continue
            try:
                previous[number] = signal.signal(number, lambda *_: self.stop("sinal do sistema"))
            except (ValueError, OSError):
                pass
        return previous

    def run(self):
        slug = self.cam["slug"]
        stop_file = self.out / "stop"
        if stop_file.exists():
            stop_file.unlink()
        self.spool = Spool(self.out / "spool")
        self.writer = Writer(self.spool)
        self.recovered = len(self.spool.pending(10_000_000)[0])
        previous = self.install_signals()
        try:
            item = self.open()
            if self.threaded:
                self.writer.start()
            self.loop(item)
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
            if self.frames is not None:
                self.frames.close()
            if self.stream is not None:
                self.stream.close()
            drained = self.writer.finish() if self.threaded and self.writer.thread is not None else self.writer.drain()
            self.state = "stopped"
            self.publish()
            if stop_file.exists():
                stop_file.unlink()
        return {
            "slug": slug,
            "frames": self.pipe.frames,
            "counted": self.counted,
            "stored": self.writer.stored,
            "recovered": self.recovered,
            "fps": self.pipe.fps(),
            "decider": "simulation labels" if self.use_truth else self.version,
            "busy": self.writer.busy,
            "drained": drained,
            "dropped": self.frames.dropped if self.frames else 0,
            "reconnects": self.frames.reconnects if self.frames else 0,
            "reason": self.reason,
        }

    def loop(self, item):
        cam, slug = self.cam, self.cam["slug"]
        first_t = item[0]
        wall0, base = time.perf_counter(), timezone.now()
        last_snap, seq = -1e9, 0
        self.state = "running"
        while item is not None or self.live:
            if self.stop_requested():
                self.reason = self.reason or "arquivo de parada"
                break
            if item is None:
                self.state = self.frames.state if self.frames.state != "running" else "stalled"
                self.publish()
                item = self.read()
                continue
            self.state = "running"
            t, frame, wall = item
            self.t = t
            due = t - last_snap >= self.snapshot_every
            began = time.perf_counter()
            passages, image = self.pipe.process(t, frame, draw=due)
            spent = (time.perf_counter() - began) * 1000
            self.process_ms = spent if not self.process_ms else 0.9 * self.process_ms + 0.1 * spent
            if passages:
                if self.simulated and self.fast:
                    moment = base + timedelta(seconds=t)
                elif wall is not None:
                    moment = datetime.fromtimestamp(wall, dt_timezone.utc)
                else:
                    moment = timezone.now()
                records = []
                for p in passages:
                    seq += 1
                    records.append(ingest.passage_record(cam, p, f"{slug}:{self.boot}:{seq}", moment, self.lot, self.simulated, self.version))
                self.spool.append(records)
                self.counted += len(records)
                self.writer.wake.set()
            if not self.threaded and self.spool.backlog_bytes():
                self.writer.step()
            if due:
                last_snap = t
                ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if ok:
                    write_atomic(self.out / "frame.jpg", jpeg.tobytes())
                self.publish()
            if self.seconds is not None and t - first_t >= self.seconds:
                break
            if self.simulated and not self.fast:
                ahead = (t - first_t) - (time.perf_counter() - wall0)
                if ahead > 0:
                    self.halt.wait(ahead)
            item = self.read()
