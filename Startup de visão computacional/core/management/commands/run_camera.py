import time
from datetime import timedelta

import cv2
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError
from django.utils import timezone

from belt.classify import CropClassifier, ModelDecider, TruthDecider
from belt.pipeline import BeltPipeline
from belt.simulate import SimulatedBelt
from belt.source import CameraSource

from ...cameras import camera as find_camera
from ...cameras import passage_event, run_dir, write_atomic, write_status
from ...models import Event


class Command(BaseCommand):
    help = "Read a camera (RTSP, USB index, video file or 'sim'), count and classify each fruit that crosses the line, and store one event per fruit."

    def add_arguments(self, parser):
        parser.add_argument("camera")
        parser.add_argument("--source", help="overrides the source in config/cameras.json")
        parser.add_argument("--lot", default="")
        parser.add_argument("--seconds", type=float)
        parser.add_argument("--decider", choices=["auto", "model", "truth"], default="auto")
        parser.add_argument("--fast", action="store_true", help="simulation only: do not wait for real time")
        parser.add_argument("--snapshot-every", type=float, default=0.5)

    def handle(self, *args, camera: str, source, lot, seconds, decider, fast, snapshot_every, **options):
        cam = find_camera(camera)
        if cam is None:
            raise CommandError(f"unknown camera {camera!r}; see {settings.CAMERAS_FILE}")
        spec = source or cam["source"]
        simulated = spec == "sim"
        if decider == "truth" and not simulated:
            raise CommandError("--decider truth only exists for the simulator")
        if simulated:
            belt = SimulatedBelt(px_per_mm=cam["px_per_mm"], **cam.get("sim", {}))
            read, width, kind = belt.read, belt.width, "simulação"
        else:
            stream = CameraSource(spec)
            read, width, kind = stream.read, None, "câmera"
        use_truth = simulated and decider in ("auto", "truth")
        if use_truth:
            version = "simulacao"
            decide = TruthDecider(belt)
            stamp = "SIMULAÇÃO · rótulos da simulação"
        else:
            classifier = CropClassifier(settings.MODEL_PATH)
            version = classifier.version
            decide = ModelDecider(classifier, cam.get("min_size_mm"))
            stamp = "SIMULAÇÃO · modelo em frutas sintéticas" if simulated else None
        first_t, frame = read()
        if frame is None:
            raise CommandError(f"no frames from {spec!r}")
        pipe = BeltPipeline(decide, cam["px_per_mm"], width or frame.shape[1], cam.get("count_line", 0.62), cam.get("direction", 1), tuple(cam["belt_rows"]) if cam.get("belt_rows") else None, camera=cam["slug"], stamp=stamp)
        wall0, base = time.perf_counter(), timezone.now()
        last_snap, total, pending, locked = -1e9, 0, [], 0
        out = run_dir(cam["slug"])
        t = first_t
        while frame is not None:
            due = t - last_snap >= snapshot_every
            passages, image = pipe.process(t, frame, draw=due)
            if passages:
                stamp_time = (base + timedelta(seconds=t)) if simulated and fast else timezone.now()
                pending += [passage_event(cam, p, stamp_time, lot, simulated, version) for p in passages]
            if pending:
                try:
                    Event.objects.bulk_create(pending)
                    total += len(pending)
                    pending = []
                except OperationalError:
                    locked += 1
            if due:
                last_snap = t
                ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if ok:
                    write_atomic(out / "frame.jpg", jpeg.tobytes())
                write_status(cam["slug"], source=kind, decider="simulação" if use_truth else "modelo", model_version=version, lot=lot, fps=round(pipe.fps(), 1), frames=pipe.frames, passages=total, stream_seconds=round(t, 1))
            if seconds is not None and t - first_t >= seconds:
                break
            if simulated and not fast:
                ahead = (t - first_t) - (time.perf_counter() - wall0)
                if ahead > 0:
                    time.sleep(ahead)
            t, frame = read()
        if not simulated:
            stream.close()
        for attempt in range(20):
            if not pending:
                break
            try:
                Event.objects.bulk_create(pending)
                total += len(pending)
                pending = []
            except OperationalError:
                locked += 1
                time.sleep(0.5 * (attempt + 1))
        if pending:
            raise CommandError(f"{len(pending)} counted fruits could not be stored: the database stayed locked")
        self.stdout.write(f"{cam['slug']}: {pipe.frames} frames, {total} fruits counted, {pipe.fps():.1f} frames/s, decided by {'simulation labels' if use_truth else version}; database busy {locked} times, nothing lost")
