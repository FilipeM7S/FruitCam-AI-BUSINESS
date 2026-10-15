import time

from django.core.management.base import BaseCommand

from ... import rollups
from ...models import DayCount, MinuteStat


class Command(BaseCommand):
    help = "Recompute the per-minute and per-day aggregates from the stored events."

    def add_arguments(self, parser):
        parser.add_argument("--if-needed", action="store_true", help="only when the aggregates are out of step with the events")

    def handle(self, *args, if_needed, **options):
        rollups.ensure_triggers()
        if if_needed and rollups.in_sync():
            self.stdout.write("agregados em dia; nada a fazer")
            return
        started = time.perf_counter()
        events = rollups.rebuild()
        self.stdout.write(f"{events} eventos lidos em {time.perf_counter() - started:.1f} s: {MinuteStat.objects.count()} minutos de linha e {DayCount.objects.count()} contagens diárias gravados")
