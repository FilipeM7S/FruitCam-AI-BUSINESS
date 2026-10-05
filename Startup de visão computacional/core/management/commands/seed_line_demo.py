from datetime import timedelta

import numpy as np
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ...cameras import cameras
from ...models import Event

LABELS = ("boa", "baixa_qualidade", "podre")
SIZE_MM = {"boa": (56, 4), "baixa_qualidade": (42, 5), "podre": (50, 5)}


class Command(BaseCommand):
    help = "Replace the synthetic camera events with simulated line traffic: per-fruit events, lots, and one lot with a rotten-rate shift."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=float, default=8.0)
        parser.add_argument("--seed", type=int, default=0)
        parser.add_argument("--lot-minutes", type=int, default=90)
        parser.add_argument("--shift-lot", type=int, default=3)
        parser.add_argument("--review-share", type=float, default=0.03)

    def handle(self, *args, hours, seed, lot_minutes, shift_lot, review_share, **options):
        rng = np.random.default_rng(seed)
        end = timezone.now().replace(second=0, microsecond=0)
        start = end - timedelta(hours=hours)
        rows = []
        for c_index, cam in enumerate(cameras()):
            rate = cam.get("sim", {}).get("rate_per_s", 1.5)
            base_mix = np.asarray(cam.get("sim", {}).get("mix", [0.6, 0.25, 0.15]), float)
            t = start
            minute = 0
            while t < end:
                lot_index = minute // lot_minutes
                lot = f"L{c_index + 1}-{start:%m%d}-{lot_index + 1:02d}"
                mix = base_mix.copy()
                if c_index == 0 and lot_index + 1 == shift_lot:
                    mix = np.array([0.45, 0.2, 0.35])
                mix /= mix.sum()
                arrivals = np.sort(rng.uniform(0, 60, rng.poisson(rate * 60)))
                labels = rng.choice(3, size=len(arrivals), p=mix)
                for s, k in zip(arrivals, labels):
                    label = LABELS[k]
                    mean, sd = SIZE_MM[label]
                    review = bool(rng.random() < review_share)
                    rows.append(Event(
                        timestamp=t + timedelta(seconds=float(s)), sector=cam["line"], fruit_type=cam["fruit_type"],
                        is_good=label == "boa", deformity_type=None if label == "boa" else label,
                        confidence=float(np.clip(rng.beta(12, 1.5), 0.34, 1.0)), is_demo=True, source="camera", camera=cam["slug"],
                        lot=lot, track_id=len(rows) + 1, label=label, size_mm=float(rng.normal(mean, sd)), needs_review=review,
                        decided_by="simulacao", model_version="simulacao",
                    ))
                t += timedelta(minutes=1)
                minute += 1
        with transaction.atomic():
            Event.objects.filter(is_demo=True, source="camera").delete()
            Event.objects.bulk_create(rows, batch_size=5000)
        self.stdout.write(f"line demo events: {len(rows)} over {hours:g} h for {len(cameras())} cameras (lot {shift_lot} of the first camera has a rotten-rate shift)")
