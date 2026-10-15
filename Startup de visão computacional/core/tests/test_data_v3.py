import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from unittest import mock

import numpy as np
from django.conf import settings
from django.test import SimpleTestCase

from belt.classify import CropClassifier
from belt.composite import composite
from core.certificate_text import DECLARATIONS
from core.tests.test_api import show
from core.tests.test_legal import REGISTRY, load_tool
from training import cashew_data as D

ROOT = settings.BASE_DIR
REMOTE = load_tool("remote_zip")
CARD_COUNTS = {"cashew_tree": 1107, "flower": 16757, "immature": 11766, "mature": 4244, "ripe": 11721, "spoilt": 518}


def archive():
    rng = np.random.default_rng(0)
    members = {"labels.txt": b"tree\nflower\n", "Images/1.JPG": rng.integers(0, 256, 40_000, dtype=np.uint8).tobytes(), "Images/2.JPG": rng.integers(0, 256, 30_000, dtype=np.uint8).tobytes(), "Labels/1.txt": b"3 0.5 0.5 0.1 0.1\n" * 40, "Labels/2.txt": b"4 0.2 0.2 0.05 0.05\n" * 25}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, data in members.items():
            z.writestr(name, data, zipfile.ZIP_DEFLATED if name.endswith(".txt") else zipfile.ZIP_STORED)
    return buffer.getvalue(), members


class RemoteArchiveTests(SimpleTestCase):
    def setUp(self):
        self.data, self.members = archive()
        self.requests = []
        self.folder = Path(tempfile.mkdtemp(prefix="fruitcam_remote_"))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def serve(self, url, start, end, attempts=8):
        self.requests.append((start, end))
        return self.data[start:end]

    def test_index_and_single_files_are_read_with_range_requests_only(self):
        with mock.patch.object(REMOTE, "fetch", self.serve):
            entries, cost = REMOTE.index("https://example.invalid/a.zip", len(self.data))
            after_index = len(self.requests)
            labels = [e for e in entries if e["name"].startswith("Labels/")]
            done = REMOTE.mirror("https://example.invalid/a.zip", len(self.data), labels, self.folder)
            again = REMOTE.mirror("https://example.invalid/a.zip", len(self.data), labels, self.folder)
        fetched = sum(b - a for a, b in self.requests[after_index:])
        show(f"archive of {len(self.data):,} B with {len(entries)} files: index read with {cost['requests']} range request(s); 2 label files fetched with {done['requests']} request(s) covering {fetched:,} B; second run fetched {again['files']} files")
        self.assertEqual(sorted(e["name"] for e in entries), sorted(self.members))
        self.assertEqual(done["files"], 2)
        self.assertEqual(done["requests"], 1)
        self.assertLess(fetched, 2000)
        self.assertEqual((again["files"], again["skipped"]), (0, 2))
        for name in ("Labels/1.txt", "Labels/2.txt"):
            self.assertEqual((self.folder / name).read_bytes(), self.members[name])

    def test_a_changed_byte_is_caught_by_the_checksum_in_the_index(self):
        with mock.patch.object(REMOTE, "fetch", self.serve):
            entries, _ = REMOTE.index("https://example.invalid/a.zip", len(self.data))
        photo = next(e for e in entries if e["name"] == "Images/1.JPG")
        damaged = bytearray(self.data)
        damaged[photo["offset"] + 200] ^= 0xFF
        self.data = bytes(damaged)
        with mock.patch.object(REMOTE, "fetch", self.serve):
            with self.assertRaises(ValueError) as caught:
                REMOTE.mirror("https://example.invalid/a.zip", len(self.data), [photo], self.folder)
        show(f"one byte flipped inside {photo['name']}: {caught.exception}; file written: {(self.folder / photo['name']).exists()}")
        self.assertIn("CRC-32", str(caught.exception))
        self.assertFalse((self.folder / photo["name"]).exists())

    def test_distant_files_are_not_fetched_in_one_request(self):
        with mock.patch.object(REMOTE, "fetch", self.serve):
            entries, _ = REMOTE.index("https://example.invalid/a.zip", len(self.data))
        wanted = [e for e in entries if e["name"] in ("labels.txt", "Labels/2.txt")]
        groups = list(REMOTE.batches(wanted, gap=1000))
        self.assertEqual([len(g) for g in groups], [1, 1])


class LabelOrderTests(SimpleTestCase):
    def test_order_is_read_from_where_the_tree_box_is(self):
        tree_first = [(0, 0.5, 0.5, 0.99, 0.9), (4, 0.2, 0.2, 0.05, 0.05)]
        tree_last = [(5, 0.5, 0.5, 0.95, 0.99), (3, 0.2, 0.2, 0.05, 0.05)]
        self.assertEqual(D.label_order(tree_first), "paper")
        self.assertEqual(D.label_order(tree_last), "alpha")
        self.assertIsNone(D.label_order([(1, 0.5, 0.5, 0.1, 0.1)]))
        self.assertIsNone(D.label_order(tree_first + tree_last))
        self.assertEqual(D.ORDER_PAPER, {2: "premature", 3: "unripe", 4: "ripe", 5: "spoilt"})
        self.assertEqual(D.ORDER_ALPHA, {1: "premature", 2: "unripe", 3: "ripe", 4: "spoilt"})
        self.assertEqual({D.PRODUCT[s] for s in D.STAGES}, set(D.CLASSES))

    def test_local_uganda_labels_split_into_two_batches(self):
        orders = Counter(D.label_order(D.rows_of(p)) for p in sorted(D.SOURCES["uganda"]["labels"].glob("*.txt")))
        show(f"Uganda label files: {orders['paper']} with the tree as class 0 (order of the paper), {orders['alpha']} with the tree as class 5 (alphabetical order), {orders[None]} without a usable tree box")
        self.assertEqual((orders["paper"], orders["alpha"], orders[None]), (1589, 1440, 69))

    def test_ghana_label_counts_match_the_published_card_only_in_alphabetical_order(self):
        labels = D.SOURCES["ghana"]["labels"]
        if not labels.exists():
            self.skipTest(f"the Ghana labels are not on this machine ({labels}); run python tools/fetch_cashew_drone.py --labels-only")
        per_id = Counter()
        for p in labels.glob("*.txt"):
            per_id.update(c for c, *_ in D.rows_of(p))
        alphabetical = dict(zip(sorted(n.replace("cashew_", "") for n in CARD_COUNTS), (per_id[i] for i in range(6))))
        listed = dict(zip(CARD_COUNTS, (per_id[i] for i in range(6))))
        card = {k.replace("cashew_", ""): v for k, v in CARD_COUNTS.items()}
        show(f"boxes per class id in the Ghana files: {dict(sorted(per_id.items()))}; read alphabetically: {alphabetical}; published card: {card}")
        self.assertEqual(alphabetical, card)
        self.assertNotEqual({k.replace('cashew_', ''): v for k, v in listed.items()}, card)


def br(value, digits=0):
    return f"{100 * value:.{digits}f}".replace(".", ",") + "%"


class ModelV3Tests(SimpleTestCase):
    def setUp(self):
        self.report = json.loads((ROOT / "models" / "belt_v3_eval.json").read_text(encoding="utf-8"))
        self.compare = json.loads((ROOT / "models" / "compare_v3.json").read_text(encoding="utf-8"))
        self.figures = json.loads((ROOT / "frontend" / "src" / "figures.json").read_text(encoding="utf-8"))["modelEval"]

    def test_configured_model_is_the_one_the_site_describes(self):
        weights = settings.MODEL_PATH
        digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        classifier = CropClassifier(weights)
        show(f"configured {weights.name}; evaluation file describes {self.report['model']['file']}; figures describe {self.figures['model']['file']}; sha256 equal to the evaluation file: {digest == self.report['model']['sha256']}; automatic decision threshold in the weights: {classifier.reject_below}")
        self.assertEqual(weights.name, self.report["model"]["file"])
        self.assertEqual(weights.name, self.figures["model"]["file"])
        self.assertEqual(digest, self.report["model"]["sha256"])
        self.assertIsNone(classifier.reject_below)
        self.assertTrue(classifier.needs_review(0.999))
        self.assertEqual(self.figures["test"]["n"], self.report["test"]["n"])
        self.assertEqual(self.figures["test"]["balanced_accuracy"], self.report["test"]["balanced_accuracy"])
        self.assertIsNone(self.figures["test"]["with_reject"]["threshold"])
        self.assertEqual(self.figures["test"]["field_photo_threshold"], self.report["test"]["field_photo_threshold"])

    def test_first_uganda_batch_is_in_no_split_of_the_model(self):
        used = self.report["data"]["sources_used"]
        photos = self.report["test_predictions"]["photo"]
        show(f"sources used by the model: {used}; test crops by source prefix: {dict(Counter(p.split(':')[0] for p in photos))}")
        self.assertEqual(sorted(used), ["ghana", "uganda_b"])
        self.assertEqual({p.split(":")[0] for p in photos}, {"ghana", "uganda_b"})
        self.assertEqual(sum(self.report["data"]["counts"]["test"].values()), self.report["test"]["n"])

    def test_numbers_quoted_in_the_declarations_come_from_the_result_files(self):
        test = self.report["test"]
        video = self.compare["models"]["belt_v3"]["held_out_real_video_backgrounds"]["balanced_accuracy"]
        old = self.compare["models"]["belt_v2"]["field_photo_test"]["balanced_accuracy"]
        train = self.report["data"]["counts"]["train"]
        total = f"{sum(train.values()):,}".replace(",", ".")
        limits = [f"{br(test['balanced_accuracy'])} de acurácia balanceada", f"cai para {br(video)}", f"({train['podre']} no treino)", f"cerca de {round(100 * test['per_class']['podre']['precision'])} estavam certos"]
        origin = [f"{total} recortes", f"acurácia balanceada de {br(old)} e o atual, {br(test['balanced_accuracy'])}"]
        show(f"limits text must contain {limits}; data text must contain {origin}")
        for piece in limits:
            self.assertIn(piece, DECLARATIONS["limits"])
        for piece in origin:
            self.assertIn(piece, DECLARATIONS["dataIssue"])
        counting = json.loads((ROOT / "assets" / "figures" / "data" / "belt_eval.json").read_text(encoding="utf-8"))["counting"]
        self.assertEqual(counting, self.figures["belt"]["counting"])
        self.assertIn(f"{counting['counted']} contagens para {counting['fruits_that_crossed_the_line']} frutas", DECLARATIONS["verified"][0])
        self.assertIn(f"para {counting['double_counts']} em {counting['fruits_that_crossed_the_line']} frutas reais", next(x["text"] for x in DECLARATIONS["pending"] if x["title"] == "Fruta da cor da esteira"))

    def test_model_reproduces_the_stored_test_predictions(self):
        if not (D.OUT / "manifest.csv").exists():
            self.skipTest(f"the crops are not on this machine ({D.OUT}); run python tools/fetch_cashew_drone.py and python -m training.cashew_data")
        rows = {r["key"]: r for r in D.manifest()}
        stored = self.report["test_predictions"]
        picked = list(range(0, len(stored["key"]), 4))
        files = D.CropFiles([], None)
        classifier = CropClassifier(ROOT / "models" / "belt_v3.pt")
        crops = [np.asarray(files.image(rows[stored["key"][i]]))[:, :, ::-1].copy() for i in picked]
        probs = np.vstack([classifier.probs(crops[i:i + 64]) for i in range(0, len(crops), 64)])
        kept = np.array(stored["p"])[picked]
        y = np.array(stored["y"])[picked]
        worst = float(np.abs(probs - kept).max())
        same = int((probs.argmax(1) == kept.argmax(1)).sum())
        labels = [D.CLASSES.index(rows[stored["key"][i]]["label"]) for i in picked]
        show(f"pure-torch MobileNetV3-Small vs predictions stored at training time: {len(picked)} of {len(stored['key'])} test crops (every fourth), largest probability difference {worst:.1e}, same class on {same} of {len(picked)}, labels equal to the stored ones {labels == y.tolist()}, accuracy on this sample {float((probs.argmax(1) == y).mean()):.4f}")
        self.assertEqual(labels, y.tolist())
        self.assertLess(worst, 5e-5)
        self.assertEqual(same, len(picked))


class RealBackgroundTests(SimpleTestCase):
    def test_composite_takes_its_background_from_the_video_pictures(self):
        crop = np.full((64, 64, 3), 200, np.uint8)
        mask = np.zeros((64, 64), np.uint8)
        mask[24:40, 24:40] = 1
        green = np.zeros((90, 120, 3), np.uint8)
        green[..., 1] = 180
        rng = np.random.default_rng(0)
        out, name = composite(crop, mask, rng, bank=[green], bank_share=1.0)
        corner = out[:6, :6].reshape(-1, 3).mean(axis=0)
        plain, plain_name = composite(crop, mask, np.random.default_rng(0), bank=[green], bank_share=0.0)
        show(f"background source '{name}': corner colour {corner.round().tolist()}; with share 0 the background is the synthetic belt '{plain_name}'")
        self.assertEqual(name, "video")
        self.assertGreater(corner[1], 3 * max(corner[0], corner[2], 1))
        self.assertNotEqual(plain_name, "video")
        self.assertGreater(out[30, 30].min(), 120)


class NewSourcesTests(SimpleTestCase):
    def test_new_sets_are_registered_with_accepted_licences_and_cards(self):
        registered = {d["id"]: d for d in REGISTRY["datasets"]}
        meta = {d["id"]: d for d in json.loads((ROOT / "scripts" / "datasets.json").read_text(encoding="utf-8"))["datasets"]}
        for name in ("cashew_drone_full", "usda_line_videos", "apple_grading_video"):
            card = (ROOT / "data" / "external" / name / "SOURCE.md").read_text(encoding="utf-8")
            show(f"{name}: licence in the registry '{registered[name]['license']}'; files in the manifest {len(meta[name]['files'])}; card points to LICENSES.md: {'LICENSES.md' in card}")
            self.assertIn(registered[name]["license"], REGISTRY["policy"]["datasets"])
            self.assertIn(f"entry `{name}`", card)
        self.assertTrue(all("sha1" in f for f in meta["usda_line_videos"]["files"]))
        self.assertIn("Não entra no treino", registered["apple_grading_video"]["use"])
        partial = [f["name"] for f in meta["cashew_drone_full"]["files"] if f.get("partial")]
        self.assertEqual(partial, ["ghana_cashew.zip", "uganda_cashew.zip"])
        self.assertIn("## Partial download", (ROOT / "data" / "external" / "cashew_drone_full" / "SOURCE.md").read_text(encoding="utf-8"))


class FineTuneFieldMixTests(SimpleTestCase):
    def test_old_loader_gives_wrong_classes_for_a_file_in_the_other_order(self):
        from PIL import Image

        from training import train_belt

        folder = Path(tempfile.mkdtemp(prefix="fruitcam_order_"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        Image.new("RGB", (400, 400), (90, 140, 70)).save(folder / "photo.jpg")
        (folder / "photo.txt").write_text("5 0.5 0.5 0.99 0.99\n3 0.3 0.3 0.2 0.2\n4 0.7 0.7 0.2 0.2\n", encoding="utf-8")
        rows = D.rows_of(folder / "photo.txt")
        order = D.label_order(rows)
        right = {c: D.PRODUCT[D.ORDER_ALPHA[c]] for c, *_ in rows if c in D.ORDER_ALPHA}
        old = {int(it["key"].split(":")[1]): train_belt.CLASSES[it["label"]] for it in train_belt.load_crops(folder, folder, 24, 0.15, 0)}
        show(f"one label file in alphabetical order (tree as class 5, a ripe fruit as class 3, a spoilt fruit as class 4): order detected '{order}'; classes by the checked reading {right}; classes by the old loader, row by row, {old}")
        self.assertEqual(order, "alpha")
        self.assertEqual(right, {3: "boa", 4: "podre"})
        self.assertEqual(old, {0: "podre", 1: "baixa_qualidade", 2: "boa"})

    def test_fine_tuning_mixes_in_only_training_crops_of_the_checked_batches(self):
        from PIL import Image

        tool = load_tool("finetune_belt")
        rows = [{"key": f"{source}__p{i}__{stage}", "source": source, "photo": f"p{i}", "split": split, "stage": stage, "label": D.PRODUCT[stage]} for source in ("ghana", "uganda_a", "uganda_b") for i, split in enumerate(("train", "train", "val", "test")) for stage in D.STAGES]

        class Files:
            def __init__(self, *a, **k):
                pass

            def image(self, row):
                return Image.new("RGB", (32, 32), (10, 10, 10))

        store = Path(tempfile.mkdtemp(prefix="fruitcam_store_"))
        self.addCleanup(shutil.rmtree, store, ignore_errors=True)
        (store / "manifest.csv").write_text("key", encoding="utf-8")
        with mock.patch.object(D, "manifest", lambda: rows), mock.patch.object(D, "CropFiles", Files), mock.patch.object(D, "OUT", store):
            items, sources = tool.field_items(ROOT / "models" / "belt_v3.pt", 100, 0)
        origin = Counter(it["photo"].split(":")[0] for it in items)
        source = (ROOT / "tools" / "finetune_belt.py").read_text(encoding="utf-8")
        show(f"manifest with 3 sources x 4 photos x 4 stages: sources taken {sources}; crops mixed in by origin {dict(origin)}; splits {sorted({it['split'] for it in items})}; classes {dict(Counter(D.CLASSES[it['label']] for it in items))}; the tool still calls the old loader: {'load_crops' in source}")
        self.assertEqual(sorted(sources), ["ghana", "uganda_b"])
        self.assertEqual(set(origin), {"ghana", "uganda_b"})
        self.assertEqual(len(items), 2 * 2 * 4)
        self.assertEqual({it["split"] for it in items}, {"train"})
        self.assertTrue(all(D.CLASSES[it["label"]] == D.PRODUCT[it["source"]] for it in items))
        self.assertNotIn("load_crops", source)
