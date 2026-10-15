import math
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone

import numpy as np
import pandas as pd
from django.db import connection, transaction
from django.db.models import F, Max
from django.utils import timezone

from .models import DayCount, Event, MinuteStat, RollupState

LABELS = ("boa", "baixa_qualidade", "podre")
CATEGORIES = (*LABELS, "revisar")
BIN_MM = 0.5
FIELDS = ("timestamp", "sector", "fruit_type", "is_good", "deformity_type", "is_demo", "source", "camera", "lot", "label", "size_mm", "needs_review")
DAY_COLUMNS = ["timestamp", "sector", "fruit_type", "is_good", "deformity_type", "n"]
FLUSH_EVERY = 50_000
UTC = dt_timezone.utc
TRIGGERS = {
    "core_event_rollup_insert": "AFTER INSERT",
    "core_event_rollup_delete": "AFTER DELETE",
    "core_event_rollup_update": "AFTER UPDATE",
}


def ensure_triggers():
    if connection.vendor != "sqlite":
        return False
    state = RollupState._meta.db_table
    with connection.cursor() as cursor:
        for name, moment in TRIGGERS.items():
            cursor.execute(
                f"CREATE TRIGGER IF NOT EXISTS {name} {moment} ON {Event._meta.db_table} BEGIN "
                f"INSERT OR IGNORE INTO {state} (id, mutations, synced) VALUES (1, 0, 0); "
                f"UPDATE {state} SET mutations = mutations + 1 WHERE id = 1; END"
            )
    return True


def triggers():
    if connection.vendor != "sqlite":
        return []
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = %s ORDER BY name", [Event._meta.db_table])
        return [row[0] for row in cursor.fetchall()]


def state():
    return RollupState.objects.filter(pk=1).first()


def in_sync():
    s = state()
    return connection.vendor == "sqlite" and (s is None and not Event.objects.exists() or s is not None and s.mutations == s.synced)


def usable(start=None):
    if connection.vendor != "sqlite":
        return False
    s = state()
    if s is None:
        return not Event.objects.exists()
    if s.mutations == s.synced:
        return True
    return bool(s.horizon and (start is None or start < s.horizon))


def version():
    s = state()
    last = Event.objects.aggregate(last=Max("id"))["last"]
    return f"{s.mutations if s else 0}.{last or 0}"


def category(label, needs_review):
    return "revisar" if needs_review or label not in LABELS else label


def size_bin(size_mm):
    return str(int(math.floor(size_mm / BIN_MM)))


def size_summary(hist):
    if not hist:
        return None
    bins = np.array(sorted(int(b) for b in hist))
    counts = np.array([hist[str(b)] if str(b) in hist else hist[b] for b in bins])
    values = (bins + 0.5) * BIN_MM
    cum = np.cumsum(counts)
    n = int(cum[-1])

    def quantile(p):
        h = (n - 1) * p
        lo, hi = math.floor(h), math.ceil(h)
        a = values[np.searchsorted(cum, lo + 1)]
        b = values[np.searchsorted(cum, hi + 1)]
        return float(a + (b - a) * (h - lo))

    return {"median": quantile(0.5), "p10": quantile(0.1), "p90": quantile(0.9), "n": n}


def size_hist(sizes):
    hist = {}
    for size in sizes:
        if size is not None and size == size:
            key = size_bin(size)
            hist[key] = hist.get(key, 0) + 1
    return hist


def fold(rows, minutes, days, tz):
    for ts, sector, fruit, good, deformity, demo, source, camera, lot, label, size, review in rows:
        ts = ts.astimezone(UTC)
        if not review:
            key = (ts.astimezone(tz).date(), sector, fruit, bool(good), deformity or "", bool(demo))
            days[key] = days.get(key, 0) + 1
        if source != "camera":
            continue
        key = (camera, ts.replace(second=0, microsecond=0), lot or "", bool(demo))
        m = minutes.get(key)
        if m is None:
            m = minutes[key] = {"counts": dict.fromkeys(CATEGORIES, 0), "sizes": {}, "first": ts, "last": ts}
        m["counts"][category(label, review)] += 1
        if size is not None and size == size:
            b = size_bin(size)
            m["sizes"][b] = m["sizes"].get(b, 0) + 1
        if ts < m["first"]:
            m["first"] = ts
        if ts > m["last"]:
            m["last"] = ts


def merge_minutes(minutes):
    if not minutes:
        return
    cameras = {k[0] for k in minutes}
    stamps = {k[1] for k in minutes}
    existing = {(r.camera, r.minute, r.lot, r.is_demo): r for r in MinuteStat.objects.filter(camera__in=cameras, minute__gte=min(stamps), minute__lte=max(stamps))}
    new, changed = [], []
    for key, m in minutes.items():
        row = existing.get(key)
        if row is None:
            new.append(MinuteStat(camera=key[0], minute=key[1], lot=key[2], is_demo=key[3], sizes=dict(m["sizes"]), first=m["first"], last=m["last"], **m["counts"]))
            continue
        for c in CATEGORIES:
            setattr(row, c, getattr(row, c) + m["counts"][c])
        sizes = dict(row.sizes)
        for b, n in m["sizes"].items():
            sizes[b] = sizes.get(b, 0) + n
        row.sizes = sizes
        row.first = min(row.first, m["first"])
        row.last = max(row.last, m["last"])
        changed.append(row)
    MinuteStat.objects.bulk_create(new, batch_size=500)
    MinuteStat.objects.bulk_update(changed, [*CATEGORIES, "sizes", "first", "last"], batch_size=200)


def merge_days(days):
    if not days:
        return
    dates = {k[0] for k in days}
    existing = {(r.day, r.sector, r.fruit_type, r.is_good, r.deformity_type, r.is_demo): r for r in DayCount.objects.filter(day__gte=min(dates), day__lte=max(dates))}
    new, changed = [], []
    for key, n in days.items():
        row = existing.get(key)
        if row is None:
            new.append(DayCount(day=key[0], sector=key[1], fruit_type=key[2], is_good=key[3], deformity_type=key[4], is_demo=key[5], n=n))
        else:
            row.n += n
            changed.append(row)
    DayCount.objects.bulk_create(new, batch_size=500)
    DayCount.objects.bulk_update(changed, ["n"], batch_size=500)


def apply(events):
    minutes, days = {}, {}
    fold(([getattr(e, f) for f in FIELDS] for e in events), minutes, days, timezone.get_current_timezone())
    merge_minutes(minutes)
    merge_days(days)


def rebuild():
    tz = timezone.get_current_timezone()
    with transaction.atomic():
        s, _ = RollupState.objects.get_or_create(pk=1)
        events = Event.objects.order_by("timestamp")
        if s.horizon:
            events = events.filter(timestamp__gte=s.horizon)
            MinuteStat.objects.filter(minute__gte=s.horizon).delete()
            DayCount.objects.filter(day__gte=s.horizon.astimezone(tz).date()).delete()
        else:
            MinuteStat.objects.all().delete()
            DayCount.objects.all().delete()
        minutes, days, seen = {}, {}, 0
        for row in events.values_list(*FIELDS).iterator(chunk_size=5000):
            fold((row,), minutes, days, tz)
            seen += 1
            if seen % FLUSH_EVERY == 0:
                edge = row[0].astimezone(UTC).replace(second=0, microsecond=0)
                done = {k: m for k, m in minutes.items() if k[1] < edge}
                MinuteStat.objects.bulk_create([MinuteStat(camera=k[0], minute=k[1], lot=k[2], is_demo=k[3], sizes=m["sizes"], first=m["first"], last=m["last"], **m["counts"]) for k, m in done.items()], batch_size=500)
                for k in done:
                    del minutes[k]
        MinuteStat.objects.bulk_create([MinuteStat(camera=k[0], minute=k[1], lot=k[2], is_demo=k[3], sizes=m["sizes"], first=m["first"], last=m["last"], **m["counts"]) for k, m in minutes.items()], batch_size=500)
        DayCount.objects.bulk_create([DayCount(day=k[0], sector=k[1], fruit_type=k[2], is_good=k[3], deformity_type=k[4], is_demo=k[5], n=n) for k, n in days.items()], batch_size=500)
        s.refresh_from_db()
        s.synced = s.mutations
        s.rebuilt = timezone.now()
        s.save(update_fields=["synced", "rebuilt"])
    return seen


def ensure():
    if in_sync():
        return None
    return rebuild()


def credit(n):
    RollupState.objects.filter(pk=1).update(synced=F("synced") + n)


def line(slug, start, end, source, window, tz):
    naive = lambda ts: ts.astimezone(tz).replace(tzinfo=None)
    origin = naive(start)
    edges = pd.date_range(origin, naive(end), freq=f"{window}min")
    counts = np.zeros((max(len(edges) - 1, 0), len(CATEGORIES)), dtype=np.int64)
    qs = MinuteStat.objects.filter(camera=slug, minute__gte=start, minute__lt=end)
    if source != "all":
        qs = qs.filter(is_demo=source == "demo")
    lots, hist, demo = {}, {}, False
    for minute, lot, is_demo, *rest in qs.values_list("minute", "lot", "is_demo", *CATEGORIES, "sizes", "first", "last"):
        k, sizes, first, last = rest[:4], rest[4], rest[5], rest[6]
        index = int((naive(minute) - origin).total_seconds() // (60 * window))
        if 0 <= index < len(counts):
            counts[index] += k
        demo = demo or is_demo
        for b, n in sizes.items():
            hist[b] = hist.get(b, 0) + n
        if lot:
            entry = lots.get(lot)
            if entry is None:
                lots[lot] = {"k": list(k), "first": first, "last": last}
            else:
                entry["k"] = [a + b for a, b in zip(entry["k"], k)]
                entry["first"] = min(entry["first"], first)
                entry["last"] = max(entry["last"], last)
    if len(edges) < 2:
        table = pd.DataFrame(columns=["start", "n", *CATEGORIES])
    else:
        table = pd.DataFrame(counts, columns=list(CATEGORIES))
        table.insert(0, "start", edges[:-1])
        table["n"] = table[list(CATEGORIES)].sum(axis=1)
    found = [{"lot": lot, "counts": dict(zip(CATEGORIES, (int(v) for v in e["k"]))), "first": pd.Timestamp(naive(e["first"])), "last": pd.Timestamp(naive(e["last"]))} for lot, e in sorted(lots.items())]
    return table, found, hist, bool(demo)


def midnight(moment, tz):
    return moment is None or moment.astimezone(tz).time() == time.min


def days(source="real", sector=None, start=None, end=None):
    tz = timezone.get_current_timezone()
    qs = DayCount.objects.all()
    if source != "all":
        qs = qs.filter(is_demo=source == "demo")
    if sector:
        qs = qs.filter(sector=sector)
    if start:
        qs = qs.filter(day__gte=start.astimezone(tz).date())
    if end:
        qs = qs.filter(day__lt=end.astimezone(tz).date())
    df = pd.DataFrame(list(qs.order_by("day", "id").values_list("day", "sector", "fruit_type", "is_good", "deformity_type", "is_demo", "n")), columns=["day", "sector", "fruit_type", "is_good", "deformity_type", "is_demo", "n"])
    has_demo = bool(df["is_demo"].astype(bool).any())
    df["timestamp"] = pd.to_datetime(df["day"])
    df["is_good"] = df["is_good"].astype(bool)
    df["deformity_type"] = df["deformity_type"].where(df["deformity_type"] != "", None)
    df["n"] = df["n"].astype("int64")
    return df[DAY_COLUMNS].sort_values("timestamp", kind="stable").reset_index(drop=True), has_demo


def prune(cutoff, step=timedelta(hours=1)):
    removed = 0
    ensure()
    while True:
        with transaction.atomic():
            oldest = Event.objects.filter(source="camera", timestamp__lt=cutoff).order_by("timestamp").values_list("timestamp", flat=True).first()
            if oldest is None:
                break
            edge = min(cutoff, oldest + step)
            n, _ = Event.objects.filter(source="camera", timestamp__gte=oldest, timestamp__lt=edge).delete()
            s = RollupState.objects.get(pk=1)
            s.synced += n
            s.horizon = max(s.horizon, cutoff) if s.horizon else cutoff
            s.save(update_fields=["synced", "horizon"])
            removed += n
    return removed


def local_midnight(days_ago):
    tz = timezone.get_current_timezone()
    today = timezone.localtime(timezone.now(), tz).date()
    return datetime.combine(today - timedelta(days=days_ago), time.min, tz)
