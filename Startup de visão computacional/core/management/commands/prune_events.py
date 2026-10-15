from django.core.management.base import BaseCommand, CommandError

from ... import rollups
from ...models import Event


class Command(BaseCommand):
    help = "Delete raw camera events older than a number of days. The per-minute and per-day aggregates are kept, so charts keep their history."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, required=True, help="keep this many whole days of raw camera events")
        parser.add_argument("--yes", action="store_true", help="really delete; without it the command only reports")

    def handle(self, *args, days, yes, **options):
        if days < 1:
            raise CommandError("--days must be at least 1")
        cutoff = rollups.local_midnight(days)
        old = Event.objects.filter(source="camera", timestamp__lt=cutoff).count()
        if not yes:
            self.stdout.write(f"{old} eventos de câmera anteriores a {cutoff.date()} seriam apagados; nada foi apagado (repita com --yes)")
            return
        removed = rollups.prune(cutoff)
        self.stdout.write(f"{removed} eventos de câmera anteriores a {cutoff.date()} apagados; os agregados por minuto e por dia foram mantidos")
