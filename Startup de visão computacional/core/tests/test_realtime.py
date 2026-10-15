import io
import json
import shutil
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import numpy as np
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from analytics import fruit_analytics as FA
from belt import spool as spool_module
from belt.capture import LatestFrame
from belt.spool import Spool
from core import ingest, rollups, stats
from core.cameras import camera
from core.line_views import SPANS, WINDOWS
from core.models import DayCount, Event, MinuteStat
from core.service import LineService
from core.supervisor import Supervisor
from core.tests.test_api import PASSWORD, show, strict_json

RUN_TMP = Path(tempfile.mkdtemp(prefix="fruitcam_realtime_"))
CAMERA_LABELS = ["boa", "baixa_qualidade", "podre", "indefinido", "nao_podre"]
DEFECTS = ("baixa_qualidade", "podre")


def camera_event(rng, when, index, demo=None):
    label = str(rng.choice(CAMERA_LABELS, p=[0.5, 0.2, 0.15, 0.1, 0.05]))
    line = 1 + index % 2
    return Event(
        timestamp=when, sector=f"linha {line}", fruit_type="caju", is_good=label in ("boa", "nao_podre"),
        deformity_type=label if label in DEFECTS else None, confidence=float(rng.uniform(0.4, 1)), source="camera", camera=f"linha-{line}",
        lot=str(rng.choice(["", "L-01", "L-02", "L-03"])), label=label, size_mm=float(rng.normal(55, 9)) if rng.random() > 0.05 else None,
        needs_review=bool(label == "indefinido" or rng.random() < 0.1), is_demo=bool(index % 3 == 0) if demo is None else demo,
        track_id=index, decided_by="simulacao", model_version="teste", uid=f"t:{index}",
    )


def photo_event(rng, when, index):
    good = bool(rng.random() < 0.6)
    return Event(
        timestamp=when, sector=str(rng.choice(["setor a", "setor b", "setor c"])), fruit_type=str(rng.choice([*FA.FRUIT_TYPES, "manga"], p=[0.5, 0.25, 0.2, 0.05])),
        is_good=good, deformity_type=None if good or rng.random() < 0.05 else str(rng.choice(["podre", "queimada", "quebrada", "baixa_qualidade"])),
        confidence=float(rng.uniform(0.4, 1)), source="foto", label="boa" if good else "podre", needs_review=bool(rng.random() < 0.05), is_demo=bool(index % 3 == 0), uid=f"t:{index}",
    )


def history(n=4000, days=70, seed=7):
    rng = np.random.default_rng(seed)
    end = timezone.now().replace(second=0, microsecond=0)
    rows = []
    for i in range(n):
        when = end - timedelta(seconds=float(rng.uniform(0, days * 86400)))
        rows.append(camera_event(rng, when, i) if rng.random() < 0.5 else photo_event(rng, when, i))
    return rows


def recent(n=3000, hours=26, seed=11, start=100_000):
    rng = np.random.default_rng(seed)
    end = timezone.now()
    return [camera_event(rng, end - timedelta(seconds=float(rng.uniform(0, hours * 3600))), start + i) for i in range(n)]


def snapshot():
    minutes = sorted((m.camera, m.minute, m.lot, m.is_demo, m.boa, m.baixa_qualidade, m.podre, m.revisar, tuple(sorted(m.sizes.items())), m.first, m.last) for m in MinuteStat.objects.all())
    days = sorted(DayCount.objects.values_list("day", "sector", "fruit_type", "is_good", "deformity_type", "is_demo", "n"))
    return minutes, days


def store_in_batches(rows, size=250):
    for i in range(0, len(rows), size):
        ingest.store(rows[i:i + size])


@override_settings(RUN_DIR=RUN_TMP)
class RollupTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.force_login(get_user_model().objects.create_user("ana", password=PASSWORD))

    def test_triggers_exist_and_count_every_insert_update_and_delete(self):
        names = rollups.triggers()
        before = rollups.state().mutations
        Event.objects.create(sector="setor a", fruit_type="caju", is_good=True)
        Event.objects.filter(sector="setor a").update(sector="setor b")
        Event.objects.filter(sector="setor b").delete()
        after = rollups.state().mutations
        show(f"triggers on the event table: {names}; mutation counter {before} -> {after} after one insert, one update and one delete")
        self.assertEqual(names, sorted(rollups.TRIGGERS))
        self.assertEqual(after - before, 3)

    def test_funnel_keeps_aggregates_identical_to_a_full_rebuild(self):
        rows = history()
        self.assertTrue(rollups.in_sync())
        store_in_batches(rows)
        self.assertTrue(rollups.in_sync())
        incremental = snapshot()
        scanned = rollups.rebuild()
        rebuilt = snapshot()
        show(f"{len(rows)} events stored in batches of 250: {len(incremental[0])} line minutes and {len(incremental[1])} daily counts kept incrementally; full rebuild read {scanned} events and produced {len(rebuilt[0])} and {len(rebuilt[1])}")
        self.assertEqual(scanned, len(rows))
        self.assertEqual(incremental[0], rebuilt[0])
        self.assertEqual(incremental[1], rebuilt[1])
        self.assertEqual(sum(d[-1] for d in rebuilt[1]), Event.objects.filter(needs_review=False).count())
        self.assertEqual(sum(sum(m[4:8]) for m in rebuilt[0]), Event.objects.filter(source="camera").count())

    def test_same_passage_is_stored_once(self):
        rows = history(300)
        first = ingest.store(rows)
        before = snapshot()
        again = ingest.store([Event(**{f.name: getattr(r, f.name) for f in Event._meta.concrete_fields if f.name != "id"}) for r in rows[:120]])
        show(f"first delivery stored {len(first)} events; delivering 120 of them again stored {len(again)}; aggregates unchanged: {snapshot() == before}")
        self.assertEqual((len(first), len(again)), (300, 0))
        self.assertEqual(Event.objects.count(), 300)
        self.assertEqual(snapshot(), before)
        self.assertTrue(rollups.in_sync())

    def test_line_summary_is_identical_from_aggregates_and_from_events(self):
        store_in_batches(recent())
        frozen = timezone.now().replace(second=30, microsecond=0)
        combos = [(m, w) for m in SPANS for w in WINDOWS if w * 4 <= m]
        compared, worst = 0, 0.0
        with mock.patch("django.utils.timezone.now", return_value=frozen):
            for minutes, window in combos:
                for source in ("real", "demo", "all"):
                    query = {"camera": "linha-1", "minutes": minutes, "window": window, "source": source}
                    cache.clear()
                    self.assertTrue(rollups.usable())
                    fast = strict_json(self.client.get("/api/line", query))
                    cache.clear()
                    with mock.patch("core.rollups.usable", return_value=False):
                        slow = strict_json(self.client.get("/api/line", query))
                    self.assertEqual(fast.pop("status"), slow.pop("status"))
                    self.assertEqual(fast, slow, query)
                    self.assertGreater(fast["total"], 0)
                    compared += 1
                    end = timezone.localtime(frozen).replace(second=0, microsecond=0)
                    qs = Event.objects.filter(source="camera", camera="linha-1", timestamp__gte=end - timedelta(minutes=minutes), timestamp__lt=end, size_mm__isnull=False)
                    if source != "all":
                        qs = qs.filter(is_demo=source == "demo")
                    sizes = np.array(qs.values_list("size_mm", flat=True))
                    self.assertEqual(fast["size_mm"]["n"], len(sizes))
                    for key, q in (("median", 0.5), ("p10", 0.1), ("p90", 0.9)):
                        gap = abs(fast["size_mm"][key] - float(np.quantile(sizes, q)))
                        worst = max(worst, gap)
                        self.assertLessEqual(gap, rollups.BIN_MM)
        show(f"{compared} combinations of period, window and source: the response built from per-minute aggregates equals the response built by scanning events; size quantiles differ from the exact ones by at most {worst:.3f} mm (bins of {rollups.BIN_MM} mm)")

    def test_dashboard_is_identical_from_aggregates_and_from_events(self):
        store_in_batches(history(6000, days=140))
        tz = timezone.get_current_timezone()
        today = timezone.localtime().date()
        spans = [(None, None), (datetime.combine(today - timedelta(days=90), datetime.min.time(), tz), datetime.combine(today - timedelta(days=6), datetime.min.time(), tz))]
        compared = 0
        for source in ("real", "demo", "all"):
            for sector in (None, "setor a", "linha 1"):
                for start, end in spans:
                    self.assertTrue(rollups.usable(start))
                    daily, demo_a = stats.load(source, sector, start, end)
                    events, demo_b = stats.load_events(source, sector, start, end)
                    self.assertIn("n", daily.columns)
                    self.assertEqual((demo_a, int(daily["n"].sum())), (demo_b, len(events)))
                    for period in ("week", "month"):
                        for name, build in stats.BUILDERS.items():
                            self.assertEqual(stats.clean(build(daily, period)), stats.clean(build(events, period)), (name, period, source, sector, start))
                            compared += 1
        api = strict_json(self.client.get("/api/stats/overview", {"source": "all"}))
        show(f"{compared} dashboard results (7 builders x 2 periods x 3 sources x 3 sector filters x 2 date ranges) are identical from {DayCount.objects.count()} daily counts and from {Event.objects.count()} events; /api/stats/overview n = {api['n']}")
        self.assertEqual(api["n"], Event.objects.filter(needs_review=False).count())

    def test_writes_outside_the_funnel_are_noticed_and_healed(self):
        store_in_batches(history(500))
        self.assertTrue(rollups.in_sync())
        Event.objects.create(sector="setor z", fruit_type="caju", is_good=False, deformity_type="podre")
        noticed = not rollups.in_sync()
        cache.clear()
        body = strict_json(self.client.get("/api/stats/overview", {"source": "real"}))
        counted = Event.objects.filter(is_demo=False, needs_review=False).count()
        healed = rollups.ensure()
        show(f"direct insert noticed: {noticed}; the dashboard fell back to events and still counted {body['n']} of {counted}; ensure() rebuilt from {healed} events; in step again: {rollups.in_sync()}")
        self.assertTrue(noticed)
        self.assertEqual(body["n"], counted)
        self.assertEqual(healed, Event.objects.count())
        self.assertTrue(rollups.in_sync())
        self.assertTrue(DayCount.objects.filter(sector="setor z", n=1).exists())
        self.assertIsNone(rollups.ensure())

    def test_size_summary_equals_numpy_on_the_binned_values(self):
        rng = np.random.default_rng(3)
        for n in (1, 2, 7, 500):
            sizes = rng.normal(55, 9, n)
            hist = rollups.size_hist(sizes)
            centres = (np.floor(sizes / rollups.BIN_MM) + 0.5) * rollups.BIN_MM
            got = rollups.size_summary(hist)
            self.assertEqual(got["n"], n)
            for key, q in (("median", 0.5), ("p10", 0.1), ("p90", 0.9)):
                self.assertAlmostEqual(got[key], float(np.quantile(centres, q)), places=9)
        self.assertIsNone(rollups.size_summary({}))

    def test_pruning_raw_events_keeps_the_history_in_the_aggregates(self):
        store_in_batches(history(3000, days=30))
        cache.clear()
        before = strict_json(self.client.get("/api/stats/overview", {"source": "all"}))
        minutes_before = MinuteStat.objects.count()
        cutoff = rollups.local_midnight(7)
        old = Event.objects.filter(source="camera", timestamp__lt=cutoff).count()
        out = io.StringIO()
        call_command("prune_events", days=7, stdout=out)
        untouched = Event.objects.filter(source="camera", timestamp__lt=cutoff).count()
        call_command("prune_events", days=7, yes=True, stdout=out)
        cache.clear()
        after = strict_json(self.client.get("/api/stats/overview", {"source": "all"}))
        state = rollups.state()
        Event.objects.create(sector="setor a", fruit_type="caju", is_good=True)
        rollups.rebuild()
        cache.clear()
        later = strict_json(self.client.get("/api/stats/overview", {"source": "all"}))
        show(out.getvalue().strip().replace(chr(10), " | "))
        show(f"dry run deleted {old - untouched}; real run left {Event.objects.filter(source='camera', timestamp__lt=cutoff).count()} old camera events; dashboard n {before['n']} -> {after['n']} -> {later['n']} after one new event and a rebuild; line minutes {minutes_before} -> {MinuteStat.objects.count()}; horizon {state.horizon}")
        self.assertGreater(old, 100)
        self.assertEqual(untouched, old)
        self.assertEqual(Event.objects.filter(source="camera", timestamp__lt=cutoff).count(), 0)
        self.assertEqual(after, before)
        self.assertEqual(later["n"], before["n"] + 1)
        self.assertEqual(MinuteStat.objects.count(), minutes_before)
        self.assertEqual(state.horizon, cutoff)
        self.assertTrue(rollups.in_sync())

    def test_seed_commands_leave_the_aggregates_in_step(self):
        call_command("seed_line_demo", hours=2, stdout=io.StringIO())
        self.assertTrue(rollups.in_sync())
        self.assertEqual(sum(m.boa + m.baixa_qualidade + m.podre + m.revisar for m in MinuteStat.objects.all()), Event.objects.filter(source="camera").count())


class LiveApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user("ana", password=PASSWORD)

    def test_health_is_short_for_strangers_and_detailed_after_login(self):
        public = strict_json(self.client.get("/api/health"))
        self.client.force_login(self.user)
        full = strict_json(self.client.get("/api/health"))
        show(f"anonymous: {public}; logged in: status {full['status']}, aggregates {full['aggregates']['in_sync']}, triggers {full['aggregates']['triggers']}, cameras {[(c['slug'], c['online']) for c in full['cameras']]}, disk free {full['disk_free_mb']} MB")
        self.assertEqual(public, {"status": "ok"})
        self.assertEqual((full["status"], full["database"], full["aggregates"]["in_sync"], full["aggregates"]["triggers"]), ("ok", True, True, 3))
        self.assertEqual([c["slug"] for c in full["cameras"]], ["linha-1", "linha-2"])

    def test_live_stream_needs_login_and_sends_the_same_summary_as_the_api(self):
        query = {"camera": "linha-1", "minutes": 60, "window": 1, "source": "all"}
        denied = self.client.get("/api/line/live", query, headers={"accept": "text/event-stream"})
        self.client.force_login(self.user)
        store_in_batches(recent(600, hours=1))
        frozen = timezone.now().replace(second=30, microsecond=0)
        with mock.patch("django.utils.timezone.now", return_value=frozen):
            expected = strict_json(self.client.get("/api/line", query))
            response = self.client.get("/api/line/live", query, headers={"accept": "text/event-stream"})
            chunks = iter(response.streaming_content)
            first, second = next(chunks), next(chunks)
            response.close()
        head, data = first.decode().strip().split(chr(10), 1)
        body = json.loads(data.removeprefix("data: "))
        show(f"without login {denied.status_code}; stream {response.status_code} {response['Content-Type']}; first message '{head}' with total {body['total']}; second message '{second.decode().splitlines()[0]}'")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual((response.status_code, response["Content-Type"], response["Cache-Control"]), (200, "text/event-stream", "no-store"))
        self.assertEqual(head, "event: summary")
        self.assertEqual({k: v for k, v in body.items() if k != "status"}, {k: v for k, v in expected.items() if k != "status"})
        self.assertEqual(second.decode().splitlines()[0], "event: status")
        bad = self.client.get("/api/line/live", {**query, "camera": "nenhuma"}, headers={"accept": "text/event-stream"})
        self.assertEqual(bad.status_code, 404)


class SpoolTests(SimpleTestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="fruitcam_spool_"))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def test_records_survive_a_restart_until_they_are_acknowledged(self):
        spool = Spool(self.folder)
        spool.append([{"uid": "a"}, {"uid": "b"}, {"uid": "c"}])
        reopened = Spool(self.folder)
        records, offset = reopened.pending()
        reopened.commit(offset)
        after = Spool(self.folder).pending()[0]
        show(f"3 records written and not acknowledged; after a restart {len(records)} are pending; after the acknowledgement {len(after)}")
        self.assertEqual([r["uid"] for r in records], ["a", "b", "c"])
        self.assertEqual(after, [])

    def test_a_torn_last_line_is_skipped_and_later_records_are_kept(self):
        spool = Spool(self.folder)
        spool.append([{"uid": "a"}])
        with spool.path.open("ab") as handle:
            handle.write(b'{"uid": "half')
        reopened = Spool(self.folder)
        reopened.append([{"uid": "b"}])
        records, offset = reopened.pending()
        show(f"file ended in the middle of a record; after restart the pending records are {[r['uid'] for r in records]} and {reopened.corrupt} torn line was skipped")
        self.assertEqual([r["uid"] for r in records], ["a", "b"])
        self.assertEqual(reopened.corrupt, 1)
        self.assertEqual(offset, reopened.path.stat().st_size)

    def test_file_is_emptied_once_everything_is_acknowledged(self):
        with mock.patch.object(spool_module, "COMPACT_BYTES", 200):
            spool = Spool(self.folder)
            spool.append([{"uid": f"u{i}", "pad": "x" * 40} for i in range(10)])
            grown = spool.path.stat().st_size
            spool.commit(spool.pending()[1])
            spool.append([{"uid": "next"}])
            records = spool.pending()[0]
        show(f"spool grew to {grown} B, was emptied after the acknowledgement, and the next record is read from offset 0: {[r['uid'] for r in records]}")
        self.assertEqual([r["uid"] for r in records], ["next"])
        self.assertEqual(Spool(self.folder).pending()[0], records)


class FakeCapture:
    def __init__(self, frames, interval=0.002):
        self.frames = frames
        self.interval = interval
        self.released = False

    def isOpened(self):
        return self.frames is not None

    def read(self):
        if not self.frames:
            return False, None
        time.sleep(self.interval)
        self.frames -= 1
        return True, np.zeros((4, 4, 3), np.uint8)

    def release(self):
        self.released = True


class GrabberTests(SimpleTestCase):
    def test_slow_reader_gets_the_newest_frame_and_the_grabber_reconnects(self):
        plan = [FakeCapture(60), FakeCapture(None), FakeCapture(10_000)]
        opened = []

        def opener(spec):
            capture = plan[min(len(opened), len(plan) - 1)]
            opened.append(capture)
            return capture

        grabber = LatestFrame("rtsp://camera", opener=opener, backoff=(0.01, 0.05)).start()
        got, states = 0, set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not (len(opened) >= 3 and got >= 25):
            item = grabber.read(timeout=0.2)
            states.add(grabber.state)
            if item is not None:
                got += 1
                time.sleep(0.02)
        grabber.close()
        show(f"camera delivered {grabber.grabbed} frames while the reader took {got}; {grabber.dropped} stale frames were skipped; connections opened {len(opened)}, reconnects {grabber.reconnects}, failures {grabber.failures}; states seen {sorted(states)}")
        self.assertGreaterEqual(got, 25)
        self.assertGreater(grabber.dropped, 0)
        self.assertEqual(grabber.grabbed, got + grabber.dropped + (grabber.seq - grabber.taken))
        self.assertGreaterEqual(len(opened), 3)
        self.assertGreaterEqual(grabber.reconnects, 1)
        self.assertTrue(plan[0].released)
        self.assertFalse(grabber.thread.is_alive())


@override_settings(RUN_DIR=RUN_TMP)
class ServiceTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(RUN_TMP, ignore_errors=True)

    def setUp(self):
        cache.clear()
        shutil.rmtree(RUN_TMP / "linha-1", ignore_errors=True)

    def test_passages_left_by_a_crashed_run_are_stored_exactly_once(self):
        cam = camera("linha-1")
        moment = timezone.now() - timedelta(minutes=3)
        left = [ingest.passage_record(cam, {"label": "podre", "confidence": 0.9, "track_id": i, "size_mm": 50.0 + i, "needs_review": False, "decided_by": "simulacao"}, f"linha-1:crash:{i}", moment, "L-9", True, "simulacao") for i in range(5)]
        Spool(RUN_TMP / "linha-1" / "spool").append(left)
        ingest.store([ingest.event_from(r) for r in left[:2]])
        result = LineService(cam, fast=True, seconds=6).run()
        again = LineService(cam, fast=True, seconds=1).run()
        crashed = Event.objects.filter(uid__startswith="linha-1:crash:").count()
        show(f"5 passages were in the spool, 2 of them already in the database; next start recovered {result['recovered']}, stored {result['stored']} (3 old + {result['counted']} new); a later start recovered {again['recovered']}; crash passages in the database: {crashed}")
        self.assertEqual(result["recovered"], 5)
        self.assertEqual(result["stored"], 3 + result["counted"])
        self.assertEqual(crashed, 5)
        self.assertEqual(again["recovered"], 0)
        self.assertTrue(result["drained"])
        self.assertTrue(rollups.in_sync())

    def test_stop_request_ends_the_run_and_nothing_is_lost(self):
        service = LineService(camera("linha-1"), seconds=60, threaded=False)
        timer = threading.Timer(7.0, lambda: (RUN_TMP / "linha-1" / "stop").write_text("stop", encoding="ascii"))
        timer.start()
        began = time.monotonic()
        result = service.run()
        took = time.monotonic() - began
        timer.cancel()
        status = json.loads((RUN_TMP / "linha-1" / "status.json").read_text(encoding="utf-8"))
        stored = Event.objects.filter(source="camera", camera="linha-1").count()
        show(f"asked to stop after 7 s of a 60 s run: ended in {took:.1f} s ({result['reason']}); counted {result['counted']}, stored {stored}; final state '{status['state']}'; stop file removed: {not (RUN_TMP / 'linha-1' / 'stop').exists()}")
        self.assertLess(took, 25)
        self.assertGreater(result["counted"], 0)
        self.assertEqual(stored, result["counted"])
        self.assertEqual((status["state"], status["passages"], status["counted"]), ("stopped", stored, stored))
        self.assertFalse((RUN_TMP / "linha-1" / "stop").exists())

    def test_status_read_survives_the_file_being_replaced(self):
        from core import cameras

        cameras.write_status("linha-1", state="running", fps=20.0)
        original = Path.read_text
        calls = {"n": 0}

        def busy(path, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise PermissionError("file is being replaced")
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", busy):
            steady = cameras.status("linha-1")
        with mock.patch.object(Path, "read_text", side_effect=PermissionError("locked")):
            locked = cameras.status("linha-1")
        missing = cameras.status("linha-9")
        show(f"status file unreadable twice in a row: online {steady['online']} after {calls['n']} reads; unreadable every time: online {locked['online']}; no file: online {missing['online']}")
        self.assertTrue(steady["online"])
        self.assertEqual(calls["n"], 3)
        self.assertEqual((locked, missing), ({"online": False}, {"online": False}))

    def test_status_reports_health_fields(self):
        call_command("run_camera", "linha-1", fast=True, seconds=5, stdout=io.StringIO())
        status = json.loads((RUN_TMP / "linha-1" / "status.json").read_text(encoding="utf-8"))
        show(f"status fields: {sorted(status)}")
        for field in ("state", "counted", "passages", "backlog_bytes", "db_busy", "dropped_frames", "reconnects", "process_ms", "pid", "started", "updated"):
            self.assertIn(field, status)
        self.assertEqual(status["backlog_bytes"], 0)
        self.assertGreater(status["process_ms"], 0)


@override_settings(RUN_DIR=RUN_TMP)
class ThreadedWriterTests(TransactionTestCase):
    def test_writer_thread_stores_every_passage_while_frames_keep_flowing(self):
        shutil.rmtree(RUN_TMP / "linha-2", ignore_errors=True)
        rollups.ensure()
        service = LineService(camera("linha-2"), seconds=5, threaded=True)
        result = service.run()
        stored = Event.objects.filter(source="camera", camera="linha-2").count()
        show(f"5 s of paced simulation with the writer in its own thread: {result['frames']} frames at {result['fps']:.1f} frames/s, counted {result['counted']}, stored {stored}, database busy {result['busy']} times, spool drained {result['drained']}; aggregates in step {rollups.in_sync()}")
        self.assertGreater(result["counted"], 2)
        self.assertEqual(stored, result["counted"])
        self.assertTrue(result["drained"])
        self.assertFalse(service.writer.thread.is_alive())
        self.assertTrue(rollups.in_sync())


class FakeProcess:
    count = 0

    def __init__(self, slug, obeys_stop=True):
        FakeProcess.count += 1
        self.pid = 1000 + FakeProcess.count
        self.slug = slug
        self.code = None
        self.obeys_stop = obeys_stop
        self.terminated = False

    def poll(self):
        if self.code is None and self.obeys_stop and (RUN_TMP / self.slug / "stop").exists():
            self.code = 0
        return self.code

    def terminate(self):
        self.terminated = True
        self.code = 1


@override_settings(RUN_DIR=RUN_TMP)
class SupervisorTests(SimpleTestCase):
    def test_dead_camera_is_restarted_with_growing_delays_and_stop_is_orderly(self):
        now = [0.0]
        spawned, log = [], []

        def spawn(slug):
            process = FakeProcess(slug, obeys_stop=slug == "linha-1")
            spawned.append(process)
            return process

        def sleep(seconds):
            now[0] += seconds

        boss = Supervisor(["linha-1", "linha-2"], spawn=spawn, clock=lambda: now[0], sleep=sleep, log=log.append)
        boss.tick()
        first = len(spawned)
        waits = []
        for _ in range(4):
            boss.children["linha-2"]["process"].code = 1
            boss.tick()
            died = now[0]
            while boss.children["linha-2"]["process"] is None:
                now[0] += 0.5
                boss.tick()
            waits.append(now[0] - died)
        now[0] += 61
        boss.tick()
        reset = boss.children["linha-2"]["delay"]
        published = json.loads((RUN_TMP / "supervisor.json").read_text(encoding="utf-8"))
        forced = boss.stop(seconds=3)
        show(f"started {first} cameras; linha-2 died 4 times and was restarted after {waits} s; after 61 s healthy the delay went back to {reset} s; restarts {published['cameras']['linha-2']['restarts']}; on stop linha-1 left by itself and {forced} had to be terminated")
        self.assertEqual(first, 2)
        self.assertEqual(waits, [1.0, 2.0, 4.0, 8.0])
        self.assertEqual(reset, 1.0)
        self.assertEqual(published["cameras"]["linha-2"]["restarts"], 4)
        self.assertEqual(published["cameras"]["linha-1"]["restarts"], 0)
        self.assertEqual(forced, ["linha-2"])
        self.assertFalse((RUN_TMP / "linha-1" / "stop").exists())
        self.assertEqual(json.loads((RUN_TMP / "supervisor.json").read_text(encoding="utf-8"))["state"], "stopped")
