import json

import numpy as np
import torch
from django.conf import settings
from django.test import SimpleTestCase

from belt.classify import CropClassifier, ModelDecider
from core.tests.test_api import show
from core.tests.test_legal import load_tool
from training import train_belt

ROOT = settings.BASE_DIR
CAL = load_tool("calibration_v3")
REPORT = ROOT / "docs" / "reports" / "calibration" / "calibration.json"


class CalibrationToolTests(SimpleTestCase):
    def test_temperature_is_recovered_from_logits_made_too_confident(self):
        rng = np.random.default_rng(0)
        true = rng.normal(0, 2.0, (6000, 3))
        p = CAL.softmax(true)
        y = np.array([rng.choice(3, p=row) for row in p])
        sharp = true * 2.5
        fitted = CAL.fit_temperature(sharp, y)
        before, after = CAL.ece(CAL.softmax(sharp), y), CAL.ece(CAL.softmax(sharp, fitted), y)
        same = train_belt.ece(torch.tensor(CAL.softmax(sharp)), torch.tensor(y))
        show(f"6,000 samples drawn from known probabilities, logits multiplied by 2.5: fitted temperature {fitted:.3f}; ECE {before:.4f} -> {after:.4f}; ECE of the training code on the same input {same:.4f}")
        self.assertAlmostEqual(fitted, 2.5, delta=0.12)
        self.assertLess(after, before / 3)
        self.assertAlmostEqual(before, same, places=5)

    def test_rotten_cut_only_moves_answers_out_of_rotten(self):
        p = np.array([[0.2, 0.3, 0.5], [0.1, 0.2, 0.7], [0.45, 0.15, 0.4], [0.05, 0.05, 0.9], [0.3, 0.6, 0.1]])
        plain, strict = CAL.decide(p, None), CAL.decide(p, 0.8)
        low = CAL.decide(p, 0.3)
        y = np.array([2, 2, 0, 2, 1])
        measured = CAL.point(p, y, 0.8)
        show(f"most probable class {plain.tolist()}; rotten only from 0.80 {strict.tolist()}; rotten from 0.30 {low.tolist()}; with the 0.80 cut: rotten precision {measured['rotten_precision']['k']}/{measured['rotten_precision']['n']}, recall {measured['rotten_recall']['k']}/{measured['rotten_recall']['n']}, rotten called good {measured['rotten_called_good']['k']}/{measured['rotten_called_good']['n']}")
        self.assertEqual(plain.tolist(), [2, 2, 0, 2, 1])
        self.assertEqual(strict.tolist(), [1, 1, 0, 2, 1])
        self.assertEqual(low.tolist(), [2, 2, 2, 2, 1])
        self.assertEqual((measured["rotten_precision"]["k"], measured["rotten_precision"]["n"]), (1, 1))
        self.assertEqual((measured["rotten_recall"]["k"], measured["rotten_recall"]["n"]), (1, 3))
        self.assertEqual(measured["rotten_called_good"]["k"], 0)

    def test_precision_recall_curve_on_a_case_solved_by_hand(self):
        score = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        positive = np.array([True, False, True, True, False])
        curve = CAL.pr_curve(score, positive)
        show(f"precision {np.round(curve['precision'], 3).tolist()} recall {np.round(curve['recall'], 3).tolist()} average precision {curve['average_precision']:.4f}")
        self.assertEqual(np.round(curve["precision"], 4).tolist(), [1.0, 0.5, 0.6667, 0.75, 0.6])
        self.assertEqual(np.round(curve["recall"], 4).tolist(), [0.3333, 0.3333, 0.6667, 1.0, 1.0])
        self.assertAlmostEqual(curve["average_precision"], (1 + 2 / 3 + 3 / 4) / 3, places=6)

    def test_near_copy_search_finds_the_planted_copy(self):
        rng = np.random.default_rng(1)
        train = rng.integers(0, 256, (300, 8), dtype=np.uint8)
        test = rng.integers(0, 256, (5, 8), dtype=np.uint8)
        test[2] = train[117]
        test[4] = train[40] ^ np.array([1, 0, 0, 0, 0, 0, 0, 2], np.uint8)
        distance = CAL.nearest(test, train, block=2)
        show(f"smallest distance to a training hash for 5 test hashes (one exact copy, one copy with 2 bits changed): {distance.tolist()}")
        self.assertEqual((int(distance[2]), int(distance[4])), (0, 2))
        self.assertTrue(all(d > 8 for d in distance[[0, 1, 3]]))


class CalibrationReportTests(SimpleTestCase):
    def setUp(self):
        self.report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.figures = json.loads((ROOT / "frontend" / "src" / "figures.json").read_text(encoding="utf-8"))

    def test_report_keeps_validation_and_test_apart_and_states_the_sizes(self):
        data, cal = self.report["data"], self.report["calibration"]
        stored = json.loads((ROOT / "models" / "belt_v3_eval.json").read_text(encoding="utf-8"))
        show(f"validation {data['validation']['crops']} crops / {data['validation']['photos']} photos; test {data['test']['crops']} crops / {data['test']['photos']} photos; photos in both {data['photos_in_both_splits']}; temperature fitted on validation {cal['temperature_fitted_on_validation']:.3f} vs {stored['model']['temperature']:.3f} in the weights; test ECE {cal['test']['ece_before']:.4f} -> {cal['test']['ece_after']:.4f} (stored at training time {stored['test_uncalibrated_ece']:.4f} -> {stored['test']['ece']:.4f})")
        self.assertEqual(data["photos_in_both_splits"], 0)
        self.assertEqual((data["test"]["crops"], data["test"]["photos"]), (stored["test"]["n"], stored["test"]["photos"]))
        self.assertEqual(data["test"]["per_class"], stored["data"]["counts"]["test"])
        self.assertAlmostEqual(cal["temperature_fitted_on_validation"], stored["model"]["temperature"], delta=0.02)
        self.assertAlmostEqual(cal["test"]["ece_before"], stored["test_uncalibrated_ece"], delta=0.003)
        self.assertAlmostEqual(cal["test"]["ece_after"], stored["test"]["ece"], delta=0.003)
        self.assertLess(cal["test"]["ece_after_ci95"][0], cal["test"]["ece_after"] + 1e-9)
        self.assertGreater(cal["test"]["ece_reduction_ci95"][0], 0)
        self.assertEqual(sum(b["n"] for b in cal["reliability_after"]), data["test"]["crops"])

    def test_default_rule_in_the_report_is_the_stored_test_result(self):
        stored = json.loads((ROOT / "models" / "belt_v3_eval.json").read_text(encoding="utf-8"))["test"]
        now = self.report["operating_point"]["test_default"]
        show(f"report default rule: rotten precision {now['rotten_precision']['k']}/{now['rotten_precision']['n']}, rotten called good {now['rotten_called_good']['k']}/{now['rotten_called_good']['n']}, balanced accuracy {now['balanced_accuracy']:.4f}; stored at training time: {stored['rotten_predicted_good']['k']}/{stored['rotten_predicted_good']['n']}, {stored['balanced_accuracy']:.4f}")
        self.assertEqual((now["rotten_called_good"]["k"], now["rotten_called_good"]["n"]), (stored["rotten_predicted_good"]["k"], stored["rotten_predicted_good"]["n"]))
        self.assertAlmostEqual(now["balanced_accuracy"], stored["balanced_accuracy"], places=3)
        self.assertAlmostEqual(now["rotten_precision"]["value"], stored["per_class"]["podre"]["precision"], places=3)

    def test_a_cut_that_breaks_the_limit_on_test_is_not_proposed_and_the_site_says_so(self):
        op = self.report["operating_point"]
        tried, shown = op["test_proposed"], self.figures["modelEval"]["rotten"]
        chosen = max(v["cut"] for v in op["validation"] if v["cut"] is not None and v["rotten_called_good"]["value"] <= 0.05)
        strings = (ROOT / "frontend" / "src" / "strings.js").read_text(encoding="utf-8")
        view = (ROOT / "frontend" / "src" / "views" / "HowItWorksView.vue").read_text(encoding="utf-8")
        show(f"cut chosen on validation {op['proposed_cut']}; on test: rotten called good {tried['rotten_called_good']['k']}/{tried['rotten_called_good']['n']} = {tried['rotten_called_good']['value']:.3f} (limit 0.05), rotten precision {tried['rotten_precision']['value']:.3f}; holds {op['holds_on_test']}; shown on the site: holds {shown['holds']}, cut {shown['cut']}")
        self.assertEqual(op["proposed_cut"], chosen)
        self.assertEqual(op["holds_on_test"], tried["rotten_called_good"]["value"] <= 0.05)
        self.assertEqual(shown["holds"], op["holds_on_test"])
        self.assertEqual(shown["tried"]["rotten_called_good"], tried["rotten_called_good"]["value"])
        self.assertEqual(shown["now"]["rotten_precision"], op["test_default"]["rotten_precision"]["value"])
        self.assertIn("Resultado negativo: a regra não mudou.", strings)
        self.assertIn("rot.holds ? t.how.rottenHolds : t.how.rottenFails", view)
        self.assertIn("fig9-podre", self.figures["order"])

    def test_app_still_answers_the_most_probable_class_and_reviews_every_fruit(self):
        classifier = CropClassifier(settings.MODEL_PATH)
        seen = {}

        def probs(crops):
            return np.array([[0.30, 0.25, 0.45]] * len(crops), np.float32)

        classifier.probs = probs
        answer = ModelDecider(classifier)({"views": [np.zeros((8, 8, 3), np.uint8)], "sizes": [50.0]})
        seen.update(answer)
        show(f"probabilities boa 0.30, baixa 0.25, podre 0.45 -> the app answers {seen['label']} with needs_review {seen['needs_review']}; cut in the weights {classifier.reject_below}")
        self.assertEqual(answer["label"], "podre")
        self.assertTrue(answer["needs_review"])
        self.assertIsNone(classifier.reject_below)


DIAG = load_tool("diagnose_uganda")
DIAGNOSIS = ROOT / "docs" / "reports" / "uganda_diagnosis"


class UgandaDiagnosisTests(SimpleTestCase):
    def test_published_table_is_the_raw_count_of_each_class_id_over_both_batches(self):
        files = DIAG.label_files()
        table, paper = DIAG.label_table({k: v for k, v in files.items() if k != "ghana"})
        spoilt = {s: table[s]["classes"][str(DIAG.NAMES[s].index("spoilt"))]["per_file"] for s in ("uganda_a", "uganda_b")}
        show(f"files per batch: {[(k, len(v)) for k, v in files.items() if k != 'ghana']}; published vs counted by id: {[(k, v['published'], v['boxes_with_this_id_in_all_uganda_files']) for k, v in paper.items()]}; boxes labelled spoilt per photo: {({k: round(v, 1) for k, v in spoilt.items()})}")
        for name, row in paper.items():
            self.assertEqual(row["published"], row["boxes_with_this_id_in_all_uganda_files"], name)
        self.assertGreater(spoilt["uganda_a"], 10 * spoilt["uganda_b"])
        self.assertEqual(table["uganda_b"]["classes"]["5"]["boxes"], 1753)

    def test_report_numbers_support_what_the_report_concludes(self):
        stats = json.loads((DIAGNOSIS / "stats.json").read_text(encoding="utf-8"))
        probe = stats["colour_probe"]
        trusted, first = probe["check_on_held_out_trusted_crops"]["ripe"], probe["first_batch_by_its_label"]["ripe"]
        size = {s: stats["labels"][s]["classes"][str(DIAG.NAMES[s].index("ripe"))]["median_height"] for s in ("uganda_a", "uganda_b")}
        registry = json.loads((ROOT / "legal" / "registry.json").read_text(encoding="utf-8"))
        registered = [d["id"] for d in registry["datasets"] if any(x["where"] == "docs/reports/uganda_diagnosis" for x in d.get("derived", []))]
        sheets = sorted(p.name for p in DIAGNOSIS.glob("*.jpg"))
        show(f"colour probe: held-out trusted ripe crops called ripe {trusted['answers']['ripe']}/{trusted['n']}; first-batch crops labelled ripe called ripe {first['answers']['ripe']}/{first['n']}; median height of a ripe box, share of the photo: {size}; sheets {sheets}; registered under {registered}")
        self.assertGreater(trusted["answers"]["ripe"] / trusted["n"], 0.6)
        self.assertLess(first["answers"]["ripe"] / first["n"], 0.15)
        self.assertGreater(size["uganda_b"], 2 * size["uganda_a"])
        self.assertEqual(len(sheets), 6)
        self.assertEqual(sorted(registered), ["cashew_drone_full", "cashew_makerere"])
        self.assertEqual(stats["original_photos"]["photos"], 10)


class CountingOptionTests(SimpleTestCase):
    def pair(self, shift, cut):
        make = lambda x0, y0, x1, y1: {"box": (x0 + shift, y0, x1 + shift, y1), "centroid": ((x0 + x1) / 2 + shift, (y0 + y1) / 2), "area_mm2": 400.0, "diameter_mm": 22.0, "edge": False, "cut": cut}
        return [make(80, 40, 100, 60), make(82, 55, 102, 80)]

    def counted(self, cut=False, **settings):
        from belt.track import Tracker

        tracker = Tracker(100, 1, **settings)
        total = 0
        for step in range(4):
            total += len(tracker.update(0.04 * step, self.pair(6 * step, cut), None))
        return total, tracker.merged

    def test_two_pieces_of_one_fruit_crossing_together_can_be_counted_once(self):
        off = self.counted(merge=0.0)
        default = self.counted()
        cut = self.counted(cut=True)
        loose = self.counted(merge=0.5)
        late = self.counted(merge_window=0.0)
        show(f"two boxes sharing 26% of the smaller one, crossing the line in the same frame: rule off counts {off[0]}; default tracker {default[0]} (merged {default[1]}); when the detector had cut them apart {cut[0]}; when the rule asks for 50% {loose[0]}; with a zero time window {late[0]}")
        self.assertEqual(off, (2, 0))
        self.assertEqual(default, (1, 1))
        self.assertEqual(cut, (2, 0))
        self.assertEqual(loose, (2, 0))

    def test_a_closed_cut_line_really_separates_two_touching_fruit(self):
        import cv2

        from belt.detect import BeltDetector

        frame = np.full((240, 420, 3), (42, 46, 40), np.uint8)
        cv2.circle(frame, (90, 120), 30, (60, 70, 220), -1)
        cv2.circle(frame, (250, 120), 30, (60, 70, 220), -1)
        cv2.circle(frame, (302, 120), 30, (60, 200, 220), -1)
        seen = {}
        for name, seal in (("open", False), ("closed", True)):
            found, _ = BeltDetector(1.6, seal=seal).detect(frame)
            seen[name] = sorted((round(d["centroid"][0]), d["cut"]) for d in found)
        show(f"one lone disc and two touching discs of 60 px: cut line left open to diagonal neighbours -> detections (x, cut) {seen['open']}; cut line closed -> {seen['closed']}")
        self.assertEqual(len(seen["open"]), 2)
        self.assertEqual([c for _, c in seen["closed"]], [False, True, True])
        self.assertEqual([x for x, _ in seen["closed"]][0], 90)
