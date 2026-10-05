import os
import secrets

import pandas as pd
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

import fruit_analytics as FA
from test_fruit_analytics import BASE, demo_events

from ...models import Event

SECTOR_NAMES = {"north": "norte", "south": "sul", "hills": "serra"}


class Command(BaseCommand):
    help = "Replace all demo events with synthetic ones and create or reset the demo user."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--weeks", type=int, default=104)
        parser.add_argument("--fruits-per-week", type=int, default=400)
        parser.add_argument("--seed", type=int, default=0)

    def handle(self, *args, username, weeks, fruits_per_week, seed, **options):
        password = os.environ.get("FRUITCAM_DEMO_PASSWORD") or secrets.token_urlsafe(12)
        events = FA.to_events(demo_events(seed, weeks, fruits_per_week))
        events["sector"] = events["sector"].map(SECTOR_NAMES).fillna(events["sector"])
        this_monday = pd.Timestamp.now(settings.TIME_ZONE).tz_localize(None).normalize()
        this_monday -= pd.Timedelta(days=this_monday.weekday())
        ts = events["timestamp"] + (this_monday - pd.Timedelta(weeks=weeks) - BASE)
        ts = ts.dt.tz_localize(settings.TIME_ZONE)
        with transaction.atomic():
            user, _ = get_user_model().objects.get_or_create(username=username)
            user.set_password(password)
            user.save()
            Event.objects.filter(is_demo=True).delete()
            Event.objects.bulk_create(
                [
                    Event(timestamp=t.to_pydatetime(), sector=s, fruit_type=f, is_good=g,
                          deformity_type=None if pd.isna(d) else d, user=user, is_demo=True)
                    for t, s, f, g, d in zip(ts, events["sector"], events["fruit_type"], events["is_good"], events["deformity_type"])
                ],
                batch_size=5000,
            )
        self.stdout.write(f"demo events: {len(events)} ({ts.min().date()} to {ts.max().date()})")
        if "FRUITCAM_DEMO_PASSWORD" not in os.environ:
            self.stdout.write(f"demo user: {username}  password: {password}")
        else:
            self.stdout.write(f"demo user: {username}  password: from FRUITCAM_DEMO_PASSWORD")
