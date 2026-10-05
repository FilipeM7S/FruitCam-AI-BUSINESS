import io
import json
import math
import re
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from PIL import Image
from torchvision import transforms

from django.core.management.base import CommandError

from belt import stats as BS
from belt.composite import HELD_OUT_BELTS, TRAIN_BELTS, composite, fruit_mask
from belt.dataset import read_manifest, split_by_batch
from belt.classify import CropClassifier, ModelDecider, TruthDecider
from belt.pipeline import BeltPipeline
from belt.simulate import SimulatedBelt
from core.models import Event
from core.tests import PASSWORD, show, strict_json
from train_belt import tree_as_five

RUN_TMP = Path(tempfile.mkdtemp(prefix="fruitcam_run_"))


def run_belt(seconds, **kw):
    sim = SimulatedBelt(**kw)
    pipe = BeltPipeline(TruthDecider(sim), sim.px_per_mm, sim.width, rows=(sim.top, sim.bottom))
    passages = []
    for _ in range(int(seconds * sim.fps)):
        t, frame = sim.read()
        passages += pipe.process(t, frame)[0]
    crossed = sim.next_id - sum(1 for f in sim.fruits if f["x"] < pipe.line_x)
    return sim, pipe, passages, crossed


class BeltCountingTests(SimpleTestCase):
    def check(self, rate, seed, seconds=90):
        sim, pipe, passages, crossed = run_belt(seconds, rate_per_s=rate, seed=seed)
        ids = [p["truth_id"] for p in passages]
        labels = {}
        for p in passages:
            labels[p["label"]] = labels.get(p["label"], 0) + 1
        show(f"{rate}/s for {seconds} s: {crossed} fruits crossed the line, {len(passages)} counted, {len(set(i for i in ids if i is not None))} distinct, unmatched {ids.count(None)}, classes {labels}")
        self.assertEqual(len(passages), crossed)
        self.assertEqual(ids.count(None), 0)
        self.assertEqual(len(set(ids)), len(ids))
        return sim, passages

    def test_each_fruit_is_counted_exactly_once(self):
        self.check(2.0, 5)

    def test_dense_traffic_is_still_counted_exactly_once(self):
        self.check(5.0, 6)

    def test_size_is_measured_within_a_few_percent(self):
        sim = SimulatedBelt(rate_per_s=2.5, seed=8)
        pipe = BeltPipeline(TruthDecider(sim), sim.px_per_mm, sim.width, rows=(sim.top, sim.bottom))
        ratios = {}
        for _ in range(int(60 * sim.fps)):
            t, frame = sim.read()
            for p in pipe.process(t, frame)[0]:
                fruit = next(f for f in sim.fruits if f["id"] == p["truth_id"])
                ratios.setdefault(p["label"], []).append(p["size_mm"] / (2 * math.sqrt(fruit["area_mm2"] / math.pi)))
        for label, r in ratios.items():
            show(f"{label:16s} measured/true diameter: median {np.median(r):.3f}, range {min(r):.3f}–{max(r):.3f} (n = {len(r)})")
            self.assertTrue(0.95 <= min(r) and max(r) <= 1.05, label)

    def test_model_decider_uses_calibrated_probabilities_and_review_threshold(self):
        classifier = CropClassifier(settings.MODEL_PATH)
        sim = SimulatedBelt(rate_per_s=3.0, seed=9)
        decider = ModelDecider(classifier)
        pipe = BeltPipeline(decider, sim.px_per_mm, sim.width, rows=(sim.top, sim.bottom))
        results = []
        for _ in range(int(30 * sim.fps)):
            t, frame = sim.read()
            results += pipe.process(t, frame)[0]
        show(f"model {classifier.version}: classes {classifier.classes}, temperature {classifier.temperature:.3f}, review below {classifier.reject_below}; {len(results)} fruits, {sum(r['needs_review'] for r in results)} sent to review, mean views {np.mean([r['views'] for r in results]):.1f}")
        self.assertEqual(classifier.classes, ["boa", "baixa_qualidade", "podre"])
        self.assertGreater(classifier.temperature, 0)
        self.assertTrue(results)
        for r in results:
            self.assertIn(r["label"], classifier.classes)
            self.assertAlmostEqual(sum(r["probs"].values()), 1.0, places=3)
            self.assertAlmostEqual(r["confidence"], max(r["probs"].values()), places=3)
            self.assertEqual(r["needs_review"], classifier.reject_below is None or r["confidence"] < classifier.reject_below)
            self.assertGreaterEqual(r["views"], 1)


    def test_inference_preprocessing_matches_training_exactly(self):
        classifier = CropClassifier(settings.MODEL_PATH)
        photo = Image.open(settings.BASE_DIR / "media_src" / "commons" / "caju-vermelho.jpg").convert("RGB")
        tf = transforms.Compose([transforms.Resize((classifier.size, classifier.size)), transforms.ToTensor(), transforms.Normalize(list(classifier.mean), list(classifier.std))])
        worst = 0.0
        for box in ((474, 672, 1242, 1440), (900, 700, 960, 760), (0, 0, 2560, 1760)):
            crop = photo.crop(box)
            with torch.no_grad():
                ref = torch.softmax(classifier.model(tf(crop).unsqueeze(0)) / classifier.temperature, 1)[0].numpy()
            got = classifier.probs([np.asarray(crop)[:, :, ::-1].copy()])[0]
            worst = max(worst, float(np.abs(ref - got).max()))
        show(f"largest probability difference between the camera path and the training transform over 3 crop sizes: {worst:.1e}")
        self.assertLess(worst, 1e-5)

def synthetic_line(seed, hours=8, rate=2.0, shift_lot=None, lot_minutes=90, rotten=0.14, shifted=0.35):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-10-01 06:00")
    rows = []
    for minute in range(int(hours * 60)):
        lot = minute // lot_minutes + 1
        p = shifted if lot == shift_lot else rotten
        n = rng.poisson(rate * 60)
        labels = rng.choice(3, size=n, p=[0.86 - p, 0.14, p])
        for s, k in zip(np.sort(rng.uniform(0, 60, n)), labels):
            rows.append((start + pd.Timedelta(minutes=minute, seconds=float(s)), BS.LABELS[k], False, f"L-{lot:02d}"))
    df = pd.DataFrame(rows, columns=["timestamp", "label", "needs_review", "lot"])
    return df, start, start + pd.Timedelta(hours=hours)


class LineStatisticsTests(SimpleTestCase):
    def test_wilson_matches_known_values(self):
        lo, hi = BS.wilson(0, 10)
        self.assertAlmostEqual(lo, 0.0, places=6)
        self.assertAlmostEqual(hi, 0.27753, places=4)
        lo, hi = BS.wilson(5, 20)
        show(f"Wilson 0/10 -> [0, {BS.wilson(0, 10)[1]:.5f}]; 5/20 -> [{lo:.5f}, {hi:.5f}]")
        self.assertAlmostEqual(lo, 0.11186, places=4)
        self.assertAlmostEqual(hi, 0.46871, places=4)

    def test_control_chart_flags_the_shifted_lot(self):
        df, start, end = synthetic_line(1, shift_lot=3)
        s = BS.summary(df, start, end, 15, 0.18)
        shifted = set(range(12, 18))
        flagged = {a["index"] for a in s["p_chart"]["alarms"] if a["rule"] == "acima_do_limite"}
        show(f"shifted lot = windows {sorted(shifted)}; flagged above the limit: {sorted(flagged)}; all alarms: {[(a['index'], a['rule']) for a in s['p_chart']['alarms']]}; sigma_z {s['p_chart']['sigma_z']:.2f}")
        self.assertEqual(flagged, shifted)

    def test_false_alarm_rate_when_nothing_changes(self):
        windows = alarms = 0
        for seed in range(60):
            df, start, end = synthetic_line(100 + seed)
            s = BS.summary(df, start, end, 15, 0.18)
            windows += len(s["windows"])
            alarms += sum(a["rule"] == "acima_do_limite" for a in s["p_chart"]["alarms"])
        show(f"in-control days: 60 x 8 h; {alarms} of {windows} windows above the limit ({alarms / windows:.3%}); a 3-sigma rule expects about 0.13%")
        self.assertLess(alarms / windows, 0.01)

    def test_lot_verdict_follows_the_confidence_interval(self):
        cases = [(100, 2000, "aprovado"), (600, 2000, "reprovado"), (37, 200, "inconclusivo"), (0, 0, "sem_dados")]
        for k, n, expected in cases:
            got = BS.lot_verdict(k, n, 0.18)
            show(f"{k}/{n} podres vs máximo 18% -> {got} (IC {BS.wilson(k, n)})")
            self.assertEqual(got, expected)


@override_settings(RUN_DIR=RUN_TMP, SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class CameraIntegrationTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(RUN_TMP, ignore_errors=True)

    def setUp(self):
        cache.clear()
        user = get_user_model().objects.create_user("ana", password=PASSWORD)
        self.client.force_login(user)

    def test_worker_stores_one_event_per_counted_fruit_and_publishes_a_frame(self):
        out = io.StringIO()
        call_command("run_camera", "linha-1", fast=True, seconds=20, lot="L-TESTE", stdout=out)
        counted = int(re.search(r"(\d+) fruits counted", out.getvalue()).group(1))
        events = Event.objects.filter(source="camera", camera="linha-1")
        status = json.loads((RUN_TMP / "linha-1" / "status.json").read_text(encoding="utf-8"))
        frame = (RUN_TMP / "linha-1" / "frame.jpg").read_bytes()
        cams = strict_json(self.client.get("/api/cameras"))["cameras"]
        image = self.client.get("/api/cameras/linha-1/frame")
        show(out.getvalue().strip())
        show(f"events stored {events.count()}, lot {set(events.values_list('lot', flat=True))}, demo {set(events.values_list('is_demo', flat=True))}, decided by {set(events.values_list('decided_by', flat=True))}; status passages {status['passages']}; frame {len(frame)} B; /api/cameras online {[c['status']['online'] for c in cams]}; frame endpoint {image.status_code} {image['Content-Type']} cache {image['Cache-Control']}")
        self.assertGreater(counted, 10)
        self.assertEqual(events.count(), counted)
        self.assertEqual(status["passages"], counted)
        self.assertEqual(set(events.values_list("lot", flat=True)), {"L-TESTE"})
        self.assertEqual(set(events.values_list("is_demo", flat=True)), {True})
        self.assertEqual(frame[:3], b"\xff\xd8\xff")
        self.assertTrue(cams[0]["status"]["online"])
        self.assertEqual((image.status_code, image["Content-Type"], image["Cache-Control"]), (200, "image/jpeg", "no-store"))
        image.close()
        for e in events:
            self.assertEqual(e.is_good, e.label == "boa")
            self.assertEqual(e.deformity_type, None if e.label == "boa" else e.label)

    def test_worker_survives_a_locked_database_without_losing_fruit(self):
        from unittest import mock

        from django.db import OperationalError
        from django.db.models.query import QuerySet

        original = QuerySet.bulk_create
        calls = {"n": 0}

        def flaky(qs, objs, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] <= 3:
                raise OperationalError("database is locked")
            return original(qs, objs, *args, **kwargs)

        out = io.StringIO()
        with mock.patch.object(QuerySet, "bulk_create", flaky):
            call_command("run_camera", "linha-1", fast=True, seconds=12, stdout=out)
        counted = int(re.search(r"(\d+) fruits counted", out.getvalue()).group(1))
        stored = Event.objects.filter(source="camera", camera="linha-1").count()
        show(out.getvalue().strip())
        show(f"bulk_create calls {calls['n']} (first 3 raised 'database is locked'); fruits counted {counted}, events stored {stored}")
        self.assertGreater(counted, 5)
        self.assertEqual(stored, counted)
        self.assertIn("database busy 3 times, nothing lost", out.getvalue())

    def test_line_summary_reports_counts_alarms_and_lots(self):
        call_command("seed_line_demo", hours=8, stdout=io.StringIO())
        r = strict_json(self.client.get("/api/line", {"camera": "linha-1", "minutes": 480, "window": 15, "source": "demo"}))
        end = timezone.localtime().replace(second=0, microsecond=0)
        complete = Event.objects.filter(camera="linha-1", is_demo=True, timestamp__gte=end - timedelta(minutes=480), timestamp__lt=end).count()
        verdicts = {lot["lot"][-2:]: lot["verdict"] for lot in r["lots"]}
        alarms = sorted({a["index"] for a in r["p_chart"]["alarms"] if a["rule"] == "acima_do_limite"})
        show(f"total {r['total']} (database {complete}); throughput {r['throughput_per_min']:.1f}/min; shares {[(c, round(v['share'], 3)) for c, v in r['shares'].items()]}; alarms {alarms}; verdicts {verdicts}")
        self.assertEqual(r["total"], complete)
        self.assertEqual(sum(r["counts"].values()), r["total"])
        self.assertEqual(verdicts["03"], "reprovado")
        self.assertTrue(all(v == "aprovado" for k, v in verdicts.items() if k != "03"))
        self.assertTrue(alarms)
        lot3 = next(lot for lot in r["lots"] if lot["lot"].endswith("03"))
        times = [w["start"] for i, w in enumerate(r["windows"]) if i in alarms]
        self.assertTrue(all(lot3["first"][:16] <= t[:16] <= lot3["last"][:16] for t in times), (times, lot3["first"], lot3["last"]))
        for c in BS.LABELS:
            lo, hi = r["shares"][c]["ci95"]
            self.assertLessEqual(lo, r["shares"][c]["share"])
            self.assertLessEqual(r["shares"][c]["share"], hi)

    def test_line_api_validates_input_and_requires_login(self):
        codes = [self.client.get("/api/line", q).status_code for q in ({"camera": "nope"}, {"camera": "linha-1", "minutes": 7}, {"camera": "linha-1", "window": 2}, {"camera": "linha-1", "minutes": 30, "window": 15}, {"camera": "linha-1", "source": "x"})]
        self.client.logout()
        anonymous = [self.client.get(p).status_code for p in ("/api/line?camera=linha-1", "/api/cameras", "/api/cameras/linha-1/frame")]
        show(f"invalid queries -> {codes}; without login -> {anonymous}")
        self.assertEqual(codes, [404, 400, 400, 400, 400])
        self.assertEqual(anonymous, [403, 403, 403])


class DataCollectionTests(SimpleTestCase):
    def test_tray_split_never_puts_one_tray_in_two_splits(self):
        rows = [{"label": label, "batch": f"{label}-{b}", "fruit": f"{label}-{b}/r/{i}"} for label, n in (("boa", 3), ("baixa_qualidade", 2), ("podre", 4)) for b in range(n) for i in range(40)]
        splits, info = split_by_batch(rows, 0)
        where = {}
        for name, part in splits.items():
            for r in part:
                where.setdefault(r["batch"], set()).add(name)
        test_batches = {b for b, s in where.items() if "test" in s}
        show(f"batches -> splits {dict(sorted((b, sorted(s)) for b, s in where.items()))}; notes {info['notes']}")
        self.assertTrue(all(s == {"test"} for b, s in where.items() if b in test_batches))
        self.assertEqual(sorted({r["label"] for r in splits["test"]}), ["baixa_qualidade", "boa", "podre"])
        self.assertEqual(sum(len(v) for v in splits.values()), len(rows))
        with self.assertRaises(ValueError):
            split_by_batch([r for r in rows if r["batch"] != "boa-1" and r["batch"] != "boa-2"], 0)

    def test_misnumbered_label_files_are_detected(self):
        folder = Path(tempfile.mkdtemp(prefix="fruitcam_labels_"))
        self.addCleanup(shutil.rmtree, folder, True)
        (folder / "paper.txt").write_text("0 0.5 0.5 0.98 0.97\n5 0.3 0.4 0.03 0.05\n")
        (folder / "shifted.txt").write_text("5 0.5 0.5 0.99 0.99\n0 0.2 0.2 0.1 0.12\n")
        self.assertEqual(tree_as_five(folder), {"shifted"})

    def test_fruit_mask_cuts_the_fruit_out_of_leaves(self):
        rng = np.random.default_rng(0)
        img = np.clip(rng.normal((60, 130, 50), 25, (90, 90, 3)), 0, 255).astype(np.uint8)
        yy, xx = np.mgrid[0:90, 0:90]
        disc = ((xx - 45) ** 2 / 22 ** 2 + (yy - 47) ** 2 / 28 ** 2) <= 1
        img[disc] = np.clip(rng.normal((215, 70, 40), 12, (int(disc.sum()), 3)), 0, 255).astype(np.uint8)
        mask, method = fruit_mask(img, (19, 15, 71, 79))
        iou = float((mask.astype(bool) & disc).sum() / (mask.astype(bool) | disc).sum())
        out, belt = composite(img, mask, np.random.default_rng(1), HELD_OUT_BELTS)
        background_change = float(np.abs(out[~disc].astype(int) - img[~disc].astype(int)).mean())
        show(f"mask method {method}, IoU with the true fruit {iou:.3f}; composite on '{belt}', mean background change {background_change:.0f} levels")
        self.assertEqual(method, "grabcut")
        self.assertGreater(iou, 0.85)
        self.assertIn(belt, HELD_OUT_BELTS)
        self.assertFalse(set(TRAIN_BELTS) & set(HELD_OUT_BELTS))
        self.assertGreater(background_change, 20)


@override_settings(RUN_DIR=RUN_TMP)
class RecordTrayTests(TestCase):
    def test_record_tray_saves_labelled_crops_and_no_events(self):
        out = Path(tempfile.mkdtemp(prefix="fruitcam_trays_"))
        self.addCleanup(shutil.rmtree, out, True)
        log = io.StringIO()
        call_command("record_tray", "linha-1", "--label", "podre", "--batch", "podre-A", "--source", "sim", "--seconds", "12", "--fast", "--out", str(out), stdout=log)
        rows = read_manifest(out)
        fruits = {r["fruit"] for r in rows}
        frames = list((out / "podre-A" / "frames").glob("*.jpg"))
        show(log.getvalue().strip().replace("\n", " | "))
        show(f"manifest rows {len(rows)}, fruits {len(fruits)}, labels {sorted({r['label'] for r in rows})}, full frames {len(frames)}, events in database {Event.objects.count()}")
        self.assertGreater(len(fruits), 5)
        self.assertEqual({r["label"] for r in rows}, {"podre"})
        self.assertTrue(all((out / r["file"]).exists() for r in rows))
        self.assertGreaterEqual(len(frames), 5)
        self.assertEqual(Event.objects.count(), 0)
        with self.assertRaises(CommandError):
            call_command("record_tray", "linha-1", "--label", "boa", "--batch", "podre-A", "--source", "sim", "--seconds", "2", "--fast", "--out", str(out), stdout=io.StringIO())
