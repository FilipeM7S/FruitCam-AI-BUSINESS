import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from PIL import Image

from core.tests import show

ROOT = settings.BASE_DIR
EXTERNAL = ROOT / "data" / "external"
PROCESSED = ROOT / "data" / "processed"
META = json.loads((ROOT / "scripts" / "datasets.json").read_text(encoding="utf-8"))
LABEL_MAP = json.loads((ROOT / "data" / "label_map.json").read_text(encoding="utf-8"))
LICENSES = json.loads((ROOT / "frontend" / "src" / "licenses.json").read_text(encoding="utf-8"))
SETS = {"potatoes": "potatoes", "potatoes_foreign_objects": "potatoes", "lemons": "lemons", "fruitnet": "fruitnet"}
ALLOWED = {"CC0", "CC BY 4.0", "MIT", "Apache 2.0", "CC BY-SA 4.0"}
RANK = {"good": 0, "poor": 1, "poor_or_rotten": 2, "rotten": 3}


def manifest(name):
    with (PROCESSED / name / "manifest.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def digest(path, algo):
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class DatasetFilesTests(SimpleTestCase):
    def test_archives_match_the_published_hashes(self):
        rows = []
        for ds in META["datasets"]:
            for spec in ds["files"]:
                path = EXTERNAL / ds["id"] / "raw" / spec["name"]
                for algo in ("md5", "sha256"):
                    if algo in spec:
                        got = digest(path, algo)
                        rows.append((ds["id"], spec["name"], algo, spec[algo], got, path.stat().st_size, spec["size"]))
        for r in rows:
            show(f"{r[0]:10s} {r[1]:30s} {r[2]:6s} published {r[3][:16]}… computed {r[4][:16]}… size {r[5]:,} (published {r[6]:,})")
        self.assertEqual(len({(r[0], r[1]) for r in rows}), sum(len(d["files"]) for d in META["datasets"]))
        for r in rows:
            self.assertEqual(r[3], r[4], r[:3])
            self.assertEqual(r[5], r[6], r[:2])

    def test_fetch_script_downloads_nothing_the_second_time(self):
        before = {p: p.stat().st_mtime_ns for p in EXTERNAL.rglob("raw/*") if p.is_file()}
        run = subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_datasets.py")], capture_output=True, text=True, encoding="utf-8", timeout=600)
        after = {p: p.stat().st_mtime_ns for p in EXTERNAL.rglob("raw/*") if p.is_file()}
        show(run.stdout.strip().replace("\n", " | "))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("total downloaded: 0 B", run.stdout)
        self.assertEqual(run.stdout.count("already present and verified, nothing downloaded"), len(META["datasets"]))
        self.assertNotIn("downloading", run.stdout)
        self.assertEqual(before, after)

    def test_every_processed_image_opens_with_the_expected_size(self):
        report = {}
        for name in SETS:
            sizes = Counter()
            modes = Counter()
            rows = manifest(name)
            for r in rows:
                with Image.open(PROCESSED / name / r["file"]) as im:
                    im.load()
                    sizes[im.size] += 1
                    modes[im.mode] += 1
            on_disk = sum(1 for _ in (PROCESSED / name / "images").rglob("*.png"))
            report[name] = (len(rows), on_disk, dict(sizes), dict(modes))
            show(f"{name:26s} manifest rows {len(rows):6d} png files {on_disk:6d} sizes {dict(sizes)} modes {dict(modes)}")
        for name, (rows, on_disk, sizes, modes) in report.items():
            self.assertEqual(rows, on_disk, name)
            self.assertEqual(sizes, {(128, 128): rows}, name)
            self.assertEqual(modes, {"RGB": rows}, name)

    def test_every_label_is_in_the_label_map_and_follows_it(self):
        vocabulary = set(LABEL_MAP["vocabulary"]) | set(LABEL_MAP["foreign_object_labels"])
        mismatches = []
        for name, ds in SETS.items():
            classes = LABEL_MAP["datasets"][ds]["classes"]
            rows = manifest(name)
            labels = {r["label"] for r in rows}
            folders = {p.name for p in (PROCESSED / name / "images").glob("*/*") if p.is_dir()}
            show(f"{name:26s} labels on disk {sorted(labels)}; label folders {sorted(folders)}")
            self.assertTrue(labels <= vocabulary, name)
            self.assertTrue(folders <= vocabulary, name)
            for r in rows:
                if ds == "potatoes":
                    entry = classes[r["source_label"]]
                    expected = entry.get("foreign_object") if entry["to"] == "ignore" else entry["to"]
                elif ds == "lemons":
                    mapped = [classes[c]["to"] for c in r["source_label"].split("+") if c != "none" and classes[c]["to"] != "ignore"]
                    expected = max(mapped, key=RANK.get) if mapped else "good"
                else:
                    expected = classes[r["source_label"].split("/")[0]]["to"]
                if expected != r["label"] or f"/{r['label']}/" not in r["file"]:
                    mismatches.append((name, r["file"], r["source_label"], r["label"], expected))
        show(f"rows whose label does not follow data/label_map.json: {len(mismatches)}")
        self.assertEqual(mismatches, [])

    def test_no_object_or_fruit_is_in_two_splits(self):
        for name in SETS:
            rows = manifest(name)
            groups, objects = {}, {}
            for r in rows:
                groups.setdefault(r["group"], set()).add(r["split"])
                objects.setdefault(r["object_id"], set()).add(r["split"])
                self.assertIn(f"images/{r['split']}/", r["file"])
            split_counts = Counter(r["split"] for r in rows)
            show(f"{name:26s} groups {len(groups):6d} objects {len(objects):6d} splits {dict(split_counts)}; groups in two splits {sum(1 for s in groups.values() if len(s) > 1)}; objects in two splits {sum(1 for s in objects.values() if len(s) > 1)}")
            self.assertTrue(all(len(s) == 1 for s in groups.values()), name)
            self.assertTrue(all(len(s) == 1 for s in objects.values()), name)
            self.assertEqual(set(split_counts), {"train", "val", "test"}, name)
        fruit_split = {}
        for r in manifest("lemons"):
            fruit_split.setdefault(r["object_id"].split("_")[0], set()).add(r["split"])
        show(f"lemons: {len(fruit_split)} fruit numbers, each in exactly one split: {all(len(s) == 1 for s in fruit_split.values())}")
        self.assertTrue(all(len(s) == 1 for s in fruit_split.values()))

    def test_duplicate_check_across_splits(self):
        report = json.loads((PROCESSED / "conversion_report.json").read_text(encoding="utf-8"))
        for name in SETS:
            d = report[name]["duplicates"]
            show(f"{name:26s} exact duplicates across splits {d['exact_duplicate_images_in_two_splits']}; pHash candidates {d['phash_candidate_pairs_across_splits']}; confirmed near-duplicates {d['confirmed_near_duplicates_across_splits']} (highest candidate correlation {d['highest_candidate_correlation']})")
            self.assertEqual(report[name]["rows"], len(manifest(name)))
            self.assertEqual(d["exact_duplicate_images_in_two_splits"], 0, name)
            self.assertEqual(d["confirmed_near_duplicates_across_splits"], 0, name)
            self.assertEqual(d["groups_in_two_splits"], 0, name)

    def test_dataset_card_counts_equal_the_files_on_disk(self):
        for ds in ("potatoes", "lemons", "fruitnet"):
            card = (ROOT / "docs" / "datasets" / f"{ds}.md").read_text(encoding="utf-8")
            for name in [n for n, d in SETS.items() if d == ds]:
                block = card[card.index(f"### `{name}`"):]
                lines = [l for l in block.splitlines() if l.startswith("|")][:6]
                header = [c.strip() for c in lines[0].strip("|").split("|")]
                labels = header[1:-1]
                card_counts, disk_counts = {}, {}
                for line in lines[2:5]:
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    for label, value in zip(labels, cells[1:-1]):
                        card_counts[(cells[0], label)] = int(value)
                        disk_counts[(cells[0], label)] = sum(1 for _ in (PROCESSED / name / "images" / cells[0] / label).glob("*.png"))
                total_card = int([c.strip() for c in lines[5].strip("|").split("|")][-1])
                total_disk = sum(1 for _ in (PROCESSED / name / "images").rglob("*.png"))
                show(f"{name:26s} card {sum(card_counts.values())} (total cell {total_card}) vs disk {sum(disk_counts.values())} (all png {total_disk})")
                self.assertEqual(card_counts, disk_counts, name)
                self.assertEqual(total_card, total_disk, name)


class DatasetLicenceTests(SimpleTestCase):
    def test_every_dataset_on_disk_has_a_source_file_and_a_manifest_entry(self):
        on_disk = sorted(p.name for p in EXTERNAL.iterdir() if p.is_dir())
        declared = {d["id"]: d for d in META["datasets"]}
        manifest_ids = {d["id"] for d in LICENSES.get("datasets", [])}
        for name in on_disk:
            source = EXTERNAL / name / "SOURCE.md"
            text = source.read_text(encoding="utf-8") if source.exists() else ""
            show(f"{name:16s} SOURCE.md {source.exists()} licence {declared.get(name, {}).get('licence')!r} in licenses.json {name in manifest_ids}")
            self.assertIn(name, declared)
            self.assertTrue(source.exists(), name)
            self.assertIn(declared[name]["licence"], text)
            self.assertIn(declared[name]["attribution"], text)
            self.assertIn(name, manifest_ids)
        self.assertEqual(manifest_ids, set(declared))

    def test_gitignore_keeps_dataset_files_out_and_source_files_in(self):
        import shutil
        import tempfile

        if not shutil.which("git"):
            self.skipTest("git is not installed")
        repo = Path(tempfile.mkdtemp(prefix="fruitcam_gitignore_"))
        self.addCleanup(shutil.rmtree, repo, True)
        shutil.copy(ROOT / ".gitignore", repo / ".gitignore")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        probe = {"data/label_map.json": False, "data/external/potatoes/SOURCE.md": False, "data/external/potatoes/raw/dataset_potatoes.zip": True, "data/external/fruitnet/extracted/FruitNetDataset/a.jpg": True, "data/processed/lemons/images/train/good/a.png": True, "data/processed/lemons/manifest.csv": True, "data/processed/conversion_report.json": True}
        result = {}
        for rel in probe:
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            result[rel] = subprocess.run(["git", "check-ignore", "-q", rel], cwd=repo).returncode == 0
        show("ignored by .gitignore: " + ", ".join(f"{k} {'yes' if v else 'no'}" for k, v in result.items()))
        self.assertEqual(result, probe)

    def test_no_non_commercial_or_unclear_dataset_is_on_disk(self):
        excluded = {r["title"] for r in META["recorded_not_downloaded"]}
        names = [p.name for p in EXTERNAL.iterdir() if p.is_dir()]
        licences = {d["id"]: d["licence"] for d in META["datasets"]}
        found = [f for f in EXTERNAL.rglob("*") if f.is_file() and re.search(r"fruitroll|oranges.classification|sisfrutos", f.name, re.I)]
        show(f"datasets on disk {sorted(names)} with licences {[licences.get(n) for n in sorted(names)]}; recorded but not downloaded {sorted(excluded)}; files named after excluded sets {len(found)}")
        self.assertTrue(all(licences.get(n) in ALLOWED for n in names))
        self.assertEqual(found, [])
        for d in META["datasets"]:
            self.assertNotRegex(d["commercial_use"].lower(), r"not allowed|research only|non-commercial")
