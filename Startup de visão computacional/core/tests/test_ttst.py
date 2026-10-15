import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import torch
from django.conf import settings
from django.test import SimpleTestCase

from belt.simulate import BELT_BGR, CLASSES, SimulatedBelt
from core.tests.test_api import show
from training import ttst

ROOT = settings.BASE_DIR
MODEL = ROOT / "models" / "belt_v3.pt"
ON = {ttst.FLAG: "1"}


def drawn(n, seed):
    sim = SimulatedBelt(seed=seed)
    crops, labels = [], []
    for i in range(n):
        label = i % len(CLASSES)
        sprite, alpha, _ = sim._sprite(CLASSES[label])
        a = alpha[..., None] if alpha.ndim == 2 else alpha
        crops.append(np.clip(sprite * a + np.array(BELT_BGR, np.float32) * (1 - a), 0, 255).astype(np.uint8))
        labels.append(label)
    return crops, labels


def same(a, b):
    return all(torch.equal(a[k], b[k]) for k in a)


class BufferTests(SimpleTestCase):
    def test_only_confident_answers_enter_and_the_operator_always_wins(self):
        buffer = ttst.Buffer(threshold=0.9, per_class=2)
        crop = np.zeros((8, 8, 3), np.uint8)
        low = buffer.offer("a", crop, np.array([0.6, 0.3, 0.1]))
        high = buffer.offer("b", crop, np.array([0.95, 0.03, 0.02]))
        buffer.correct("b", crop, 2)
        again = buffer.offer("b", crop, np.array([0.99, 0.005, 0.005]))
        buffer.correct("a", crop, 1)
        for key in ("c", "d", "e"):
            buffer.offer(key, crop, np.array([0.97, 0.02, 0.01]))
        show(f"confidence 0.60 accepted {low}; 0.95 accepted {high}; pseudo-label offered after an operator correction accepted {again}; kept {dict(sorted((k, (v['label'], v['origin'])) for k, v in buffer.items.items()))}; counts {buffer.counts()}; refused {buffer.refused} of {buffer.offered}")
        self.assertEqual((low, high, again), (False, True, False))
        self.assertEqual((buffer.items["b"]["label"], buffer.items["b"]["origin"]), (2, "operator"))
        self.assertEqual((buffer.items["a"]["label"], buffer.items["a"]["origin"]), (1, "operator"))
        self.assertEqual(buffer.counts()["boa"], {"pseudo": 2, "operator": 0})
        self.assertNotIn("c", buffer.items)
        self.assertEqual(buffer.smallest_class(), 1)


class AdapterTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.work = Path(tempfile.mkdtemp(prefix="fruitcam_ttst_"))
        cls.addClassCleanup(shutil.rmtree, cls.work, True)
        crops, labels = drawn(45, 1)
        cls.control = {"keys": [f"control-{i}" for i in range(len(crops))], "crops": crops, "labels": np.array(labels)}
        cls.stream = drawn(90, 2)

    def adapter(self, name, **kw):
        return ttst.Adapter(MODEL, self.control, self.work / f"{name}.jsonl", min_per_class=10, seed=0, **kw)

    def buffer(self, shift=0):
        buffer = ttst.Buffer()
        for i, (crop, label) in enumerate(zip(*self.stream)):
            buffer.correct(f"stream-{i}", crop, (label + shift) % len(CLASSES))
        return buffer

    def test_nothing_runs_while_the_flag_is_off(self):
        adapter = self.adapter("off")
        start = {k: v.clone() for k, v in adapter.classifier.model.state_dict().items()}
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ttst.FLAG, None)
            off = ttst.enabled()
            with self.assertRaises(RuntimeError) as caught:
                adapter.step(self.buffer())
        places = [p.relative_to(ROOT).as_posix() for folder in ("belt", "core", "fruitcam") for p in (ROOT / folder).rglob("*.py") if "tests" not in p.parts and "ttst" in p.read_text(encoding="utf-8")]
        show(f"flag {ttst.FLAG} unset -> enabled {off}; step: {caught.exception}; weights changed {not same(start, adapter.classifier.model.state_dict())}; log written {adapter.log.exists()}; app files that mention the module: {places}; '{ttst.FLAG}' in settings: {ttst.FLAG in (ROOT / 'fruitcam' / 'settings.py').read_text(encoding='utf-8')}")
        self.assertFalse(off)
        self.assertTrue(same(start, adapter.classifier.model.state_dict()))
        self.assertFalse(adapter.log.exists())
        self.assertEqual(places, [])

    def test_control_items_can_never_be_trained_on(self):
        adapter = self.adapter("overlap")
        buffer = self.buffer()
        buffer.correct("control-3", self.control["crops"][3], 0)
        with mock.patch.dict(os.environ, ON), self.assertRaises(ValueError) as caught:
            adapter.step(buffer)
        show(f"buffer holding one control item: {caught.exception}")
        self.assertIn("never trained on", str(caught.exception))

    def test_a_thin_buffer_is_skipped_and_logged(self):
        adapter = self.adapter("thin")
        buffer = ttst.Buffer()
        for i in range(12):
            buffer.correct(f"s-{i}", self.stream[0][i], 0 if i < 11 else 1)
        with mock.patch.dict(os.environ, ON):
            entry = adapter.step(buffer)
        lines = [json.loads(line) for line in adapter.log.read_text(encoding="utf-8").splitlines()]
        show(f"buffer {buffer.counts()} with a minimum of 10 per class: {entry['status']} ({entry['reason']}); log lines {len(lines)}")
        self.assertEqual(entry["status"], "skipped")
        self.assertEqual([line["status"] for line in lines], ["skipped"])

    def test_correct_labels_are_accepted_within_the_update_limit(self):
        adapter = self.adapter("good", steps=6, batch=12, lr=1e-4, max_update=0.01)
        start = {k: v.clone() for k, v in adapter.classifier.model.state_dict().items()}
        with mock.patch.dict(os.environ, ON):
            entry = adapter.step(self.buffer())
        end = adapter.classifier.model.state_dict()
        moving = [k for k in start if start[k].dtype.is_floating_point]
        change = float(torch.sqrt(sum(((end[k] - start[k]) ** 2).sum() for k in moving)) / torch.sqrt(sum((start[k] ** 2).sum() for k in moving)))
        saved = torch.load(adapter.save(self.work / "belt_adapted.pt"), map_location="cpu")
        show(f"90 correctly labelled drawn fruit, 6 steps: {entry['status']}; control balanced accuracy {entry['control_before']['balanced_accuracy']:.3f} -> {entry['control_after']['balanced_accuracy']:.3f} (n = {entry['control_before']['n']}); change wanted by training {entry['relative_change_before_limit']:.4f}, limit {entry['max_update']}, measured in the weights {change:.4f}; saved model: adapted_from {saved['adapted_from']}, reject_below {saved['reject_below']}")
        self.assertEqual(entry["status"], "accepted")
        self.assertLessEqual(change, 0.01 * 1.02)
        self.assertGreater(change, 0)
        self.assertGreaterEqual(entry["control_after"]["balanced_accuracy"], entry["control_before"]["balanced_accuracy"] - 0.005)
        self.assertIsNone(saved["reject_below"])
        self.assertEqual(saved["adapted_from"], "belt_v3.pt")

    def test_wrong_labels_are_rolled_back_to_the_exact_starting_weights(self):
        adapter = self.adapter("bad", steps=30, batch=12, lr=1e-3, max_update=1.0)
        start = {k: v.clone() for k, v in adapter.classifier.model.state_dict().items()}
        with mock.patch.dict(os.environ, ON):
            entry = adapter.step(self.buffer(shift=1))
        lines = [json.loads(line) for line in adapter.log.read_text(encoding="utf-8").splitlines()]
        show(f"90 drawn fruit with every label moved to the next class, 30 steps: {entry['status']} ({entry['reason']}); control balanced accuracy {entry['control_before']['balanced_accuracy']:.3f} -> {entry['control_after']['balanced_accuracy']:.3f}; rotten recall {entry['control_before']['rotten_recall']:.3f} -> {entry['control_after']['rotten_recall']:.3f}; weights back to the start {same(start, adapter.classifier.model.state_dict())}; change applied {entry['relative_change_applied']}")
        self.assertEqual(entry["status"], "rolled_back")
        self.assertTrue(same(start, adapter.classifier.model.state_dict()))
        self.assertEqual(entry["relative_change_applied"], 0.0)
        self.assertLess(entry["control_after"]["balanced_accuracy"], entry["control_before"]["balanced_accuracy"])
        self.assertEqual(lines[-1]["status"], "rolled_back")
        for key in ("at", "update", "base_model", "buffer", "steps", "lr", "control_before", "control_after", "relative_change_before_limit"):
            self.assertIn(key, lines[-1])


class ExperimentReportTests(SimpleTestCase):
    def test_report_keeps_the_three_sets_apart_and_logs_every_update(self):
        report = json.loads((ROOT / "docs" / "reports" / "ttst" / "ttst.json").read_text(encoding="utf-8"))
        log = [json.loads(line) for line in (ROOT / "docs" / "reports" / "ttst" / "updates.jsonl").read_text(encoding="utf-8").splitlines()]
        by_case = {}
        for case in report["cases"]:
            by_case.setdefault(case["case"], []).append(case)
        outcome = {name: [c["update"]["status"] for c in cases] for name, cases in by_case.items()}
        gains = {name: [round(c["target_test_after"]["balanced_accuracy"] - c["target_test_before"]["balanced_accuracy"], 3) for c in cases] for name, cases in by_case.items()}
        kept = {name: [round(c["target_test_if_the_update_had_been_kept"]["balanced_accuracy"] - c["target_test_before"]["balanced_accuracy"], 3) for c in cases if "target_test_if_the_update_had_been_kept" in c] for name, cases in by_case.items()}
        show(f"photos shared between the sets {report['photos_shared']}; background pictures shared {report['background_pictures']['shared']}; outcome per case {outcome}; change on the target test {gains}; change the refused updates would have made {kept}; log lines {len(log)}")
        self.assertEqual(set(report["photos_shared"].values()), {0})
        self.assertEqual(report["background_pictures"]["shared"], 0)
        self.assertEqual(len(log), len(report["cases"]))
        self.assertEqual([entry["status"] for entry in log], [c["update"]["status"] for c in report["cases"]])
        self.assertEqual(set(outcome["labels flipped on purpose"]), {"rolled_back"})
        self.assertTrue(all(g < -0.05 for g in kept["labels flipped on purpose"]))
        for case in report["cases"]:
            if case["update"]["status"] == "rolled_back":
                self.assertEqual(case["target_test_after"]["balanced_accuracy"], case["target_test_before"]["balanced_accuracy"])
                self.assertEqual(case["update"]["relative_change_applied"], 0.0)
            else:
                self.assertLessEqual(case["update"]["relative_change_applied"], report["settings"]["max_update"] * 1.001)
            lo, hi = case["target_gain_ci95_paired_by_photo"]
            self.assertLessEqual(lo, hi)
