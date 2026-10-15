import json
import shutil
import tempfile
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings
from django.test import SimpleTestCase

from belt.dataset import read_manifest
from belt.simulate import SimulatedBelt
from core.tests.test_api import show
from core.tests.test_legal import load_tool

ROOT = settings.BASE_DIR
CAPTURE = load_tool("capture_tray")
EVAL = load_tool("eval_real_belt")
LABELS = ("boa", "baixa_qualidade", "podre")
MODEL = ROOT / "models" / "belt_v3.pt"


def belt_video(path, label, seed, seconds=6.0):
    sim = SimulatedBelt(rate_per_s=4.0, mix=[1.0 if c == label else 0.0 for c in LABELS], seed=seed)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), sim.fps, (sim.width, sim.height))
    for _ in range(int(seconds * sim.fps)):
        writer.write(sim.read()[1])
    writer.release()
    return sim


class RealBeltKitTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.work = Path(tempfile.mkdtemp(prefix="fruitcam_kit_"))
        cls.addClassCleanup(shutil.rmtree, cls.work, True)
        cls.out = cls.work / "sessions"
        cls.runs = []
        for i, label in enumerate(LABELS):
            for j, tray in enumerate(("A", "B")):
                video = cls.work / f"{label}-{tray}.avi"
                sim = belt_video(video, label, 10 * i + j)
                cls.geometry = ["--px-per-mm", str(sim.px_per_mm), "--belt-rows", str(sim.top), str(sim.bottom)]
                cls.runs.append(CAPTURE.main(["--session", "ensaio-1", "--tray", f"{label}-{tray}", "--label", label, "--source", str(video), "--sector", "recepção", "--out", str(cls.out), *cls.geometry]))
        cls.session = cls.out / "ensaio-1"
        cls.video = cls.work / "boa-A.avi"

    def refused(self, *argv):
        with self.assertRaises(SystemExit) as caught:
            CAPTURE.main([*argv, "--out", str(self.out)])
        return str(caught.exception)

    def test_capture_refuses_to_start_without_label_session_or_fixed_camera_settings(self):
        before = sorted(p.name for p in self.out.iterdir())
        nothing = self.refused("--source", str(self.video), "--tray", "x")
        live = self.refused("--source", "0", "--session", "s", "--tray", "t", "--label", "boa", "--px-per-mm", "1.6")
        wrong = self.refused("--source", str(self.video), "--session", "s", "--tray", "t", "--label", "madura", "--px-per-mm", "1.6")
        show(f"without session, label and px/mm: {nothing.splitlines()[1:]}; live camera without settings: {live.splitlines()[1:]}; folders created by the refused runs: {sorted(set(p.name for p in self.out.iterdir()) - set(before))}")
        for piece in ("falta --session", "falta --label", "falta --px-per-mm"):
            self.assertIn(piece, nothing)
        for piece in ("falta --exposure", "falta --gain", "falta --white-balance"):
            self.assertIn(piece, live)
        self.assertIn("falta --label", wrong)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), before)

    def test_one_tray_keeps_one_label_and_one_session_keeps_one_product(self):
        relabel = self.refused("--session", "ensaio-1", "--tray", "boa-A", "--label", "podre", "--source", str(self.video), "--sector", "recepção", *self.geometry)
        product = self.refused("--session", "ensaio-1", "--tray", "nova", "--label", "boa", "--source", str(self.video), "--sector", "recepção", "--product", "manga", *self.geometry)
        show(f"tray recorded again with another label: {relabel.splitlines()[-1].strip()} | same session, other product: {product.splitlines()[-1].strip()}")
        self.assertIn("boa-A", relabel)
        self.assertIn("product", product)
        self.assertEqual(len(CAPTURE.session_of(self.session)["runs"]), 6)

    def test_every_saved_file_is_listed_with_a_checksum_and_changes_are_caught(self):
        rows = read_manifest(self.session)
        wrong, checked = CAPTURE.verify(self.session)
        listed = sum(len(r["files"]) for r in self.runs)
        card = json.loads((self.session / "boa-A" / "runs" / f"{self.runs[0]['run']}.json").read_text(encoding="utf-8"))
        victim = self.session / rows[0]["file"]
        original = victim.read_bytes()
        victim.write_bytes(original + b"0")
        changed, _ = CAPTURE.verify(self.session)
        victim.unlink()
        missing, _ = CAPTURE.verify(self.session)
        victim.write_bytes(original)
        again, _ = CAPTURE.verify(self.session)
        show(f"session ensaio-1: {len(self.runs)} runs, {sum(r['fruits'] for r in self.runs)} fruit, {len(rows)} crops in manifest.csv, {listed} files listed with SHA-256, {checked} checked, problems {wrong}; one byte added -> {changed}; file deleted -> {missing}; restored -> {again}")
        self.assertEqual(wrong, [])
        self.assertEqual(again, [])
        self.assertEqual(changed, [f"alterado: {rows[0]['file']}"])
        self.assertEqual(missing, [f"faltando: {rows[0]['file']}"])
        self.assertTrue(all(r["fruits"] >= 5 for r in self.runs))
        self.assertEqual({r["file"] for r in rows}, {f["path"] for r in self.runs for f in r["files"] if "/frames/" not in f["path"]})
        for key in ("session", "tray", "label", "product", "sector", "started_at", "ended_at", "geometry", "settings", "source_file", "software"):
            self.assertIn(key, card)
        self.assertEqual((card["label"], card["sector"], card["purpose"]), ("boa", "recepção", "real"))
        self.assertEqual(card["source_file"]["sha256"], CAPTURE.sha256(self.video))
        self.assertRegex(card["started_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

    def test_camera_password_never_reaches_the_manifest(self):
        hidden = CAPTURE.redact("rtsp://operador:senha-da-camera@10.0.0.7:554/stream1")
        show(f"rtsp address as stored: {hidden}")
        self.assertEqual(hidden, "rtsp://***@10.0.0.7:554/stream1")
        self.assertEqual(CAPTURE.redact("0"), "0")

    def test_evaluation_counts_fruit_and_keeps_trays_apart(self):
        report = EVAL.evaluate([self.session], MODEL, draws=200)
        results, data, cut = report["results"], report["data"], report["held_out_cut"]
        show(EVAL.show(report))
        self.assertIsNone(report["warning"])
        self.assertEqual(data["n_trays"], 6)
        self.assertEqual(data["n_fruits"], sum(r["fruits"] for r in self.runs))
        self.assertEqual(data["n_crops"], len(read_manifest(self.session)))
        self.assertEqual(sum(map(sum, results["confusion_rows_true_cols_called"])), data["n_fruits"])
        self.assertEqual([sum(row) for row in results["confusion_rows_true_cols_called"]], [data["per_class"][c]["fruits"] for c in LABELS])
        self.assertEqual(report["bootstrap"]["unit"], "bandeja")
        low, high = report["bootstrap"]["balanced_accuracy_ci95"]
        self.assertLessEqual(low, results["balanced_accuracy"])
        self.assertGreaterEqual(high, results["balanced_accuracy"])
        coverage = [row["coverage"] for row in report["coverage_vs_accuracy"]["rows"]]
        self.assertEqual(coverage, sorted(coverage, reverse=True))
        self.assertTrue(all(row["n"] == data["n_fruits"] for row in report["coverage_vs_accuracy"]["rows"]))
        self.assertTrue(cut["available"])
        self.assertEqual(sorted(set(cut["trays"].values())), ["fit", "report"])
        self.assertEqual(cut["fruits"]["fit"] + cut["fruits"]["report"], data["n_fruits"])
        for label in LABELS:
            self.assertEqual({cut["trays"][f"ensaio-1/{label}-{t}"] for t in ("A", "B")}, {"fit", "report"})
        self.assertIsNone(report["model"]["reject_below"])

    def test_evaluation_refuses_a_session_whose_files_changed(self):
        rows = read_manifest(self.session)
        victim = self.session / rows[-1]["file"]
        original = victim.read_bytes()
        victim.write_bytes(original[:-1])
        try:
            with self.assertRaises(SystemExit) as caught:
                EVAL.evaluate([self.session], MODEL, draws=10)
        finally:
            victim.write_bytes(original)
        show(f"evaluation of a session with one changed crop: {str(caught.exception)[:140]}")
        self.assertIn("avaliação recusada", str(caught.exception))

    def test_a_pipeline_test_session_is_marked_in_every_output(self):
        run = CAPTURE.main(["--session", "ensaio-falso", "--tray", "qualquer", "--label", "podre", "--source", str(self.video), "--pipeline-test", "--out", str(self.out), *self.geometry])
        report = EVAL.evaluate([self.out / "ensaio-falso"], MODEL, draws=50)
        mixed = self.refused("--session", "ensaio-1", "--tray", "outra", "--label", "boa", "--source", str(self.video), "--sector", "recepção", "--pipeline-test", *self.geometry)
        show(f"pipeline-test session: purpose {run['purpose']}, {run['fruits']} fruit; warning in the report: {report['warning']}; bootstrap unit {report['bootstrap']['unit']}; cut on separate trays available: {report['held_out_cut']['available']}; mixing it into a real session: {mixed.splitlines()[-1].strip()[:90]}")
        self.assertEqual(run["purpose"], "pipeline_test")
        self.assertIn("TESTE DE PIPELINE", report["warning"])
        self.assertIn("TESTE DE PIPELINE", EVAL.show(report))
        self.assertEqual(report["bootstrap"]["unit"], "fruta")
        self.assertFalse(report["held_out_cut"]["available"])
        self.assertIn("purpose", mixed)

    def test_tray_bootstrap_is_wider_than_a_fruit_bootstrap_when_trays_differ(self):
        rng = np.random.default_rng(0)
        y, pred, trays = [], [], []
        for c in range(3):
            for t, rate in enumerate((0.95, 0.55, 0.9, 0.6)):
                hits = rng.random(80) < rate
                y += [c] * 80
                pred += [c if h else (c + 1) % 3 for h in hits]
                trays += [f"{c}-{t}"] * 80
        y, pred = np.array(y), np.array(pred)
        by_tray = EVAL.bootstrap(y, pred, trays, 400, 0)
        merged = EVAL.bootstrap(y, pred, [f"{c}-0" for c in y], 400, 0)
        width = lambda b: b["balanced_accuracy_ci95"][1] - b["balanced_accuracy_ci95"][0]
        show(f"12 trays whose accuracy differs (95%, 55%, 90%, 60%): CI width resampling trays {width(by_tray):.3f} (unit {by_tray['unit']}); resampling fruit as if each class were one tray {width(merged):.3f} (unit {merged['unit']})")
        self.assertEqual((by_tray["unit"], merged["unit"]), ("bandeja", "fruta"))
        self.assertGreater(width(by_tray), 2 * width(merged))
