import argparse
import os
import statistics
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def timed(fn, repeat):
    spans = []
    for _ in range(repeat):
        began = time.perf_counter()
        fn()
        spans.append((time.perf_counter() - began) * 1000)
    return statistics.median(spans)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--line-events", type=int, default=170_000)
    parser.add_argument("--panel-events", type=int, default=150_000)
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="fruitcam_bench_"))
    os.environ["FRUITCAM_DB_PATH"] = str(work / "bench.sqlite3")
    os.environ.setdefault("DJANGO_SECRET_KEY", "bench-only")
    os.environ.setdefault("DJANGO_HTTPS", "0")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fruitcam.settings")
    import django

    django.setup()
    import numpy as np
    from django.core.cache import cache
    from django.core.management import call_command
    from django.db.models import Count, Max, Q
    from django.utils import timezone

    from core import ingest, rollups, stats
    from core.cameras import camera
    from core.line_views import line_body
    from core.models import DayCount, Event, MinuteStat

    call_command("migrate", verbosity=0)
    rng = np.random.default_rng(1)
    now = timezone.now()
    labels = np.array(["boa", "baixa_qualidade", "podre"])
    rows = []
    for i, (age, k, size, review) in enumerate(zip(rng.uniform(0, 24 * 3600, args.line_events), rng.choice(3, args.line_events, p=[0.62, 0.24, 0.14]), rng.normal(55, 9, args.line_events), rng.random(args.line_events) < 0.08)):
        label = str(labels[k])
        rows.append(Event(timestamp=now - timedelta(seconds=float(age)), sector="linha 1", fruit_type="caju", is_good=label == "boa", deformity_type=None if label == "boa" else label, confidence=0.9, source="camera", camera="linha-1", lot=f"L-{int(age // 3600):02d}", label=label, size_mm=float(size), needs_review=bool(review), track_id=i, uid=f"b:{i}"))
    sectors = np.array(["norte", "sul", "leste", "oeste", "serra", "vale", "controle"])
    fruits = np.array(["caju", "castanha", "melao"])
    for i, (age, s, f, good) in enumerate(zip(rng.uniform(0, 3 * 365 * 86400, args.panel_events), rng.choice(7, args.panel_events), rng.choice(3, args.panel_events), rng.random(args.panel_events) < 0.8)):
        rows.append(Event(timestamp=now - timedelta(seconds=float(age)), sector=str(sectors[s]), fruit_type=str(fruits[f]), is_good=bool(good), deformity_type=None if good else "podre", confidence=0.9, source="foto", label="boa" if good else "podre"))
    began = time.perf_counter()
    Event.objects.bulk_create(rows, batch_size=5000)
    load_s = time.perf_counter() - began
    began = time.perf_counter()
    scanned = rollups.rebuild()
    rebuild_s = time.perf_counter() - began
    cam = camera("linha-1")
    out = [
        f"events in the database: {Event.objects.count()} ({args.line_events} camera passages in the last 24 h, {args.panel_events} photo records over 3 years); loaded in {load_s:.1f} s",
        f"aggregates: {MinuteStat.objects.count()} line minutes and {DayCount.objects.count()} daily counts; full rebuild from {scanned} events took {rebuild_s:.1f} s",
        "",
        "median of %d runs, cache cleared before each run" % args.repeat,
        f"{'question':52s} {'from events':>12s} {'from aggregates':>16s} {'ratio':>7s}",
    ]

    def compare(name, run):
        def fresh():
            cache.clear()
            run()

        fast = timed(fresh, args.repeat)
        with mock.patch("core.rollups.usable", return_value=False):
            slow = timed(fresh, args.repeat)
        out.append(f"{name:52s} {slow:9.1f} ms {fast:13.1f} ms {slow / fast:6.1f}x")

    compare("line summary, last 24 h in 60 min windows", lambda: line_body(cam, 1440, 60, "all"))
    compare("line summary, last 60 min in 1 min windows", lambda: line_body(cam, 60, 1, "all"))
    compare("dashboard data load (all events, real)", lambda: stats.load("real"))

    def dashboard():
        events, _ = stats.load("real")
        for build in stats.BUILDERS.values():
            build(events, "week")

    compare("dashboard: load + the 7 statistics, by week", dashboard)
    old_key = timed(lambda: Event.objects.aggregate(n=Count("id"), last=Max("id"), pending=Count("id", filter=Q(needs_review=True))), args.repeat)
    new_key = timed(rollups.version, args.repeat)
    out.append(f"{'cache key: is there new data?':52s} {old_key:9.1f} ms {new_key:13.1f} ms {old_key / new_key:6.1f}x")
    out.append("")
    batch = [Event(timestamp=now, sector="linha 1", fruit_type="caju", is_good=True, confidence=0.9, source="camera", camera="linha-1", lot="L-00", label="boa", size_mm=55.0, track_id=i, uid=f"w:{i}") for i in range(2000)]
    began = time.perf_counter()
    for i in range(0, len(batch), 2):
        ingest.store(batch[i:i + 2])
    spent = time.perf_counter() - began
    out.append(f"storing 2,000 passages two at a time (event + both aggregates in one transaction): {spent:.1f} s, {spent / 1000 * 1000:.1f} ms per write, {2000 / spent:.0f} passages/s; aggregates still in step: {rollups.in_sync()}")
    size = (work / "bench.sqlite3").stat().st_size
    out.append(f"database file: {size / 1e6:.0f} MB for {Event.objects.count()} events ({size / Event.objects.count():.0f} B per event, indexes included)")
    print(chr(10).join(out))


if __name__ == "__main__":
    main()
