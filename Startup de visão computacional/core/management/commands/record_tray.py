import hashlib
import time
from pathlib import Path

import cv2
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from belt.dataset import LABELS, TrayRecorder, read_manifest
from belt.pipeline import BeltPipeline
from belt.simulate import SimulatedBelt
from belt.source import CameraSource

from ...cameras import camera as find_camera
from ...cameras import run_dir, write_atomic, write_status

SIM_CLASSES = ("boa", "baixa_qualidade", "podre")


class Command(BaseCommand):
    help = "Record a hand-sorted tray on the belt: every fruit that crosses the line is saved as crops labelled with the tray's class. Nothing is written to the statistics database."

    def add_arguments(self, parser):
        parser.add_argument("camera")
        parser.add_argument("--label", required=True, choices=LABELS)
        parser.add_argument("--batch", required=True, help="one name per physical tray, e.g. 2026-10-12-podre-A")
        parser.add_argument("--source", help="overrides the source in config/cameras.json")
        parser.add_argument("--out", default=str(Path(settings.BASE_DIR) / "belt_data"))
        parser.add_argument("--seconds", type=float)
        parser.add_argument("--frames-every", type=float, default=2.0)
        parser.add_argument("--snapshot-every", type=float, default=0.5)
        parser.add_argument("--fast", action="store_true", help="simulation only: do not wait for real time")

    def handle(self, *args, camera, label, batch, source, out, seconds, frames_every, snapshot_every, fast, **options):
        cam = find_camera(camera)
        if cam is None:
            raise CommandError(f"unknown camera {camera!r}; see {settings.CAMERAS_FILE}")
        spec = source or cam["source"]
        simulated = spec == "sim"
        try:
            recorder = TrayRecorder(out, batch, label, cam["slug"], "simulação" if simulated else spec, cam["px_per_mm"], frames_every)
        except ValueError as e:
            raise CommandError(str(e))
        if simulated:
            mix = [1.0 if c == label else 0.0 for c in SIM_CLASSES] if label in SIM_CLASSES else cam.get("sim", {}).get("mix", (0.6, 0.25, 0.15))
            sim = {**cam.get("sim", {}), "mix": mix, "seed": int(hashlib.sha256(batch.encode()).hexdigest()[:8], 16)}
            belt = SimulatedBelt(px_per_mm=cam["px_per_mm"], **sim)
            read, width = belt.read, belt.width
        else:
            stream = CameraSource(spec)
            read, width = stream.read, None
        first_t, frame = read()
        if frame is None:
            raise CommandError(f"no frames from {spec!r}")
        stamp = f"COLETA · bandeja {batch} · {label}" + (" · SIMULAÇÃO" if simulated else "")
        pipe = BeltPipeline(recorder, cam["px_per_mm"], width or frame.shape[1], cam.get("count_line", 0.62), cam.get("direction", 1), tuple(cam["belt_rows"]) if cam.get("belt_rows") else None, camera=cam["slug"], stamp=stamp)
        wall0, last_snap, t = time.perf_counter(), -1e9, first_t
        live = run_dir(cam["slug"])
        while frame is not None:
            recorder.frame(t, frame)
            due = t - last_snap >= snapshot_every
            _, image = pipe.process(t, frame, draw=due)
            if due:
                last_snap = t
                ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if ok:
                    write_atomic(live / "frame.jpg", jpeg.tobytes())
                write_status(cam["slug"], source="simulação" if simulated else "câmera", decider=f"coleta: bandeja {batch} ({label})", model_version="", lot="", fps=round(pipe.fps(), 1), frames=pipe.frames, passages=recorder.fruits, stream_seconds=round(t, 1))
            if seconds is not None and t - first_t >= seconds:
                break
            if simulated and not fast:
                ahead = (t - first_t) - (time.perf_counter() - wall0)
                if ahead > 0:
                    time.sleep(ahead)
            t, frame = read()
        if not simulated:
            stream.close()
        rows = read_manifest(out)
        per_label = {}
        for r in rows:
            per_label.setdefault(r["label"], set()).add(r["batch"])
        self.stdout.write(f"batch {batch} ({label}): {recorder.fruits} fruits, {recorder.crops} crops, {recorder.frames} full frames saved under {Path(out) / batch}")
        self.stdout.write("trays recorded so far: " + ", ".join(f"{k} {len(v)}" for k, v in sorted(per_label.items())))
        short = [k for k, v in per_label.items() if k != "sem_rotulo" and len(v) < 2]
        if short:
            self.stdout.write(f"record at least one more tray for: {', '.join(sorted(short))} (test fruit must come from a different tray)")
