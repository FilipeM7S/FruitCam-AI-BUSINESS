from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ... import rollups
from ...cameras import camera as find_camera
from ...service import LineService, ServiceError


class Command(BaseCommand):
    help = "Read a camera (RTSP, USB index, video file or 'sim'), count and classify each fruit that crosses the line, and store one event per fruit. Runs until stopped."

    def add_arguments(self, parser):
        parser.add_argument("camera")
        parser.add_argument("--source", help="overrides the source in config/cameras.json")
        parser.add_argument("--lot", default="")
        parser.add_argument("--seconds", type=float)
        parser.add_argument("--decider", choices=["auto", "model", "truth"], default="auto")
        parser.add_argument("--fast", action="store_true", help="simulation only: do not wait for real time")
        parser.add_argument("--snapshot-every", type=float, default=1 / 15)

    def handle(self, *args, camera: str, source, lot, seconds, decider, fast, snapshot_every, **options):
        cam = find_camera(camera)
        if cam is None:
            raise CommandError(f"unknown camera {camera!r}; see {settings.CAMERAS_FILE}")
        try:
            service = LineService(cam, source=source, lot=lot, seconds=seconds, decider=decider, fast=fast, snapshot_every=snapshot_every)
            rollups.ensure()
            r = service.run()
        except ServiceError as exc:
            raise CommandError(str(exc))
        tail = "nothing lost" if r["drained"] else "some fruits are still in the spool and will be stored at the next start"
        extra = f"; recovered {r['recovered']} from the previous run" if r["recovered"] else ""
        extra += f"; {r['dropped']} stale frames skipped, {r['reconnects']} reconnections" if r["dropped"] or r["reconnects"] else ""
        extra += f"; stopped by: {r['reason']}" if r["reason"] else ""
        self.stdout.write(f"{r['slug']}: {r['frames']} frames, {r['counted']} fruits counted, {r['fps']:.1f} frames/s, decided by {r['decider']}; database busy {r['busy']} times, {tail}{extra}")
