import time

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ... import rollups, showcase
from ...cameras import cameras
from ...models import Event

GOOD = ("boa",)


class Command(BaseCommand):
    help = "Replace all demo events with the showcase scenario: years of Painel history where each sector shows one statistical behaviour, plus camera traffic with lot, alarm, stop and review stories."

    def add_arguments(self, parser):
        parser.add_argument("--weeks", type=int, default=156)
        parser.add_argument("--line-hours", type=float, default=8.0)
        parser.add_argument("--seed", type=int, default=7)

    def handle(self, *args, weeks, line_hours, seed, **options):
        started = time.perf_counter()
        now = pd.Timestamp(timezone.localtime().replace(second=0, microsecond=0, tzinfo=None))
        monday = now.normalize() - pd.Timedelta(days=now.weekday())
        painel = showcase.painel_events(monday, weeks, seed)
        line_start = max(now - pd.Timedelta(hours=line_hours), monday)
        cams = {c["slug"]: c for c in cameras()}
        line = showcase.line_events(list(cams.values()), line_start, now, seed) if line_hours > 0 else pd.DataFrame()
        tz = settings.TIME_ZONE
        labels, confidences = showcase.sorting(painel, seed)
        rows = [
            Event(timestamp=t.to_pydatetime(), sector=s, fruit_type=f, is_good=bool(g), deformity_type=None if pd.isna(d) else d,
                  label=label, confidence=float(conf), is_demo=True, source="foto", decided_by="simulacao", model_version="simulacao")
            for t, s, f, g, d, label, conf in zip(painel["timestamp"].dt.tz_localize(tz), painel["sector"], painel["fruit_type"], painel["is_good"], painel["deformity_type"], labels, confidences)
        ]
        if len(line):
            rows += [
                Event(timestamp=t.to_pydatetime(), sector=cams[c]["line"], fruit_type=cams[c]["fruit_type"], is_good=label in GOOD,
                      deformity_type=None if label in GOOD else label, confidence=conf, is_demo=True, source="camera", camera=c, lot=lot,
                      track_id=i + 1, label=label, size_mm=size, needs_review=review, decided_by="simulacao", model_version="simulacao")
                for i, (t, label, review, lot, size, conf, c) in enumerate(zip(line["timestamp"].dt.tz_localize(tz), line["label"], line["needs_review"], line["lot"], line["size_mm"], line["confidence"], line["camera"]))
            ]
        with transaction.atomic():
            Event.objects.filter(is_demo=True).delete()
            Event.objects.bulk_create(rows, batch_size=5000)
            rollups.rebuild()
        self.stdout.write(f"painel: {len(painel)} events from {painel['timestamp'].min():%Y-%m-%d} to {painel['timestamp'].max():%Y-%m-%d} ({weeks} weeks)")
        for name, role in showcase.ROLES.items():
            self.stdout.write(f"  {name:9s} {role}")
        if len(line):
            self.stdout.write(f"linha: {len(line)} events from {line['timestamp'].min():%Y-%m-%d %H:%M} to {line['timestamp'].max():%H:%M} on {line['camera'].nunique()} cameras")
        self.stdout.write(f"done in {time.perf_counter() - started:.0f} s; every demo event (is_demo) was replaced, real events were not touched")
