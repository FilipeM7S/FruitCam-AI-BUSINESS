import signal
import threading
import time

from django.core.management.base import BaseCommand, CommandError

from ... import rollups
from ...cameras import cameras as configured
from ...supervisor import Supervisor, stop_file


class Command(BaseCommand):
    help = "Keep every configured camera running without pauses: one process per camera, restarted automatically if it ends. Stop with Ctrl+C or 'run_line --stop'."

    def add_arguments(self, parser):
        parser.add_argument("cameras", nargs="*")
        parser.add_argument("--seconds", type=float)
        parser.add_argument("--stop", action="store_true", help="ask a running supervisor to stop its cameras and exit")

    def handle(self, *args, cameras: list, seconds, stop, **options):
        request = stop_file()
        if stop:
            request.write_text("stop", encoding="ascii")
            self.stdout.write("pedido de parada registrado")
            return
        known = [c["slug"] for c in configured()]
        slugs = cameras or known
        unknown = [s for s in slugs if s not in known]
        if unknown:
            raise CommandError(f"unknown cameras {unknown}; configured: {known}")
        if request.exists():
            request.unlink()
        rebuilt = rollups.ensure()
        if rebuilt is not None:
            self.stdout.write(f"agregados reconstruídos a partir de {rebuilt} eventos")
        halt = threading.Event()
        previous = {}
        for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            number = getattr(signal, name, None)
            if number is not None:
                try:
                    previous[number] = signal.signal(number, lambda *_: halt.set())
                except (ValueError, OSError):
                    pass
        started = time.monotonic()
        supervisor = Supervisor(slugs, log=self.stdout.write)
        self.stdout.write(f"supervisor ligado para {', '.join(slugs)}; pare com Ctrl+C")
        try:
            supervisor.run(lambda: halt.is_set() or request.exists() or (seconds is not None and time.monotonic() - started >= seconds))
        finally:
            forced = supervisor.stop()
            for number, handler in previous.items():
                signal.signal(number, handler)
            if request.exists():
                request.unlink()
        restarts = {slug: c["restarts"] for slug, c in supervisor.children.items()}
        self.stdout.write(f"supervisor parado; reinícios por câmera {restarts}; encerradas à força {forced}")
