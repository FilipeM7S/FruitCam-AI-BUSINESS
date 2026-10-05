import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

EXTERNAL = ROOT / "data" / "external"
PROCESSED = ROOT / "data" / "processed"
LABEL_MAP = json.loads((ROOT / "data" / "label_map.json").read_text(encoding="utf-8"))
META = {d["id"]: d for d in json.loads((ROOT / "scripts" / "datasets.json").read_text(encoding="utf-8"))["datasets"]}
CARDS = ROOT / "docs" / "datasets"
SIZE = 128
NEAR = 6
CONFIRM = 0.99
FIELDS = ["file", "split", "label", "source_label", "label_basis", "object_id", "group", "source_file", "source_size"]
ORDER = ["good", "poor", "rotten", "poor_or_rotten", "plant", "stone"]
RANK = {"good": 0, "poor": 1, "poor_or_rotten": 2, "rotten": 3}


def split_of(group, seed=0):
    h = int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if h < 0.7 else "val" if h < 0.85 else "test"


def phash(rgb):
    g = cv2.resize(cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2GRAY), (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = cv2.dct(g)[:8, :8].ravel()
    return np.packbits(d > np.median(d[1:]))


POP = np.array([bin(i).count("1") for i in range(256)], np.uint8)


def near_pairs(hashes, limit):
    h = np.ascontiguousarray(np.stack(hashes)).view(np.uint64).ravel()
    pairs = []
    for i in range(0, len(h), 256):
        x = h[i:i + 256, None] ^ h[None, :]
        dist = POP[x.view(np.uint8)].reshape(x.shape[0], x.shape[1], 8).sum(2)
        for a, b in zip(*np.nonzero(dist <= limit)):
            if i + a < b:
                pairs.append((int(i + a), int(b), int(dist[a, b])))
    return pairs


def groups_from_pairs(n, pairs):
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b, _ in pairs:
        parent[find(a)] = find(b)
    return [find(i) for i in range(n)]


def save(rgb, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(rgb)).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR).save(path, optimize=True)


def potatoes():
    import eval_potatoes as ep
    files, items, merged = ep.load(0.95)
    cmap = LABEL_MAP["datasets"]["potatoes"]["classes"]
    rows = {"potatoes": [], "potatoes_foreign_objects": []}
    images = {}
    first_file = {}
    for p in files:
        a = np.asarray(Image.open(p).convert("RGB"))
        key = min(hashlib.sha1(v.tobytes()).hexdigest() for v in ep.variants(a))
        first_file.setdefault(key, p)
    for it in items:
        entry = cmap[it["label"]]
        target = "potatoes" if entry["to"] != "ignore" else "potatoes_foreign_objects"
        label = entry["to"] if target == "potatoes" else entry["foreign_object"]
        group = it["group"][:16]
        split = split_of(group)
        name = f"{it['key'][:16]}.png"
        rows[target].append({"file": f"images/{split}/{label}/{name}", "split": split, "label": label, "source_label": it["label"], "label_basis": "source_class", "object_id": it["key"][:16], "group": group, "source_file": first_file[it["key"]].relative_to(EXTERNAL / "potatoes" / "extracted").as_posix(), "source_size": "50x50"})
        images[(target, name)] = it["image"]
    before = {"files": Counter(p.parts[-2] for p in files), "unique_objects": Counter(it["label"] for it in items), "near_duplicate_pairs_merged": merged}
    return rows, images, before


def lemons():
    base = next((EXTERNAL / "lemons" / "extracted").rglob("instances_default.json"))
    root = base.parent.parent
    coco = json.loads(base.read_text(encoding="utf-8"))
    cats = {c["id"]: c["name"] for c in coco["categories"]}
    cmap = LABEL_MAP["datasets"]["lemons"]["classes"]
    regions = {}
    for a in coco["annotations"]:
        regions.setdefault(a["image_id"], set()).add(cats[a["category_id"]])
    rows, images = [], {}
    before = Counter()
    for im in coco["images"]:
        found = regions.get(im["id"], set())
        for r in found:
            before[r] += 1
        mapped = [cmap[r]["to"] for r in found if cmap[r]["to"] != "ignore"]
        label = max(mapped, key=RANK.get) if mapped else "good"
        basis = "worst_region" if mapped else "no_defect_region"
        if not mapped:
            before["no_defect_region"] += 1
        fruit = Path(im["file_name"]).stem.split("_")[0]
        split = split_of(f"lemon-{fruit}")
        stem = Path(im["file_name"]).stem
        rows.append({"file": f"images/{split}/{label}/{stem}.png", "split": split, "label": label, "source_label": "+".join(sorted(found)) or "none", "label_basis": basis, "object_id": stem, "group": f"lemon-{fruit}", "source_file": (root / im["file_name"]).relative_to(EXTERNAL / "lemons" / "extracted").as_posix(), "source_size": f"{im['width']}x{im['height']}"})
        images[("lemons", f"{stem}.png")] = root / im["file_name"]
    return {"lemons": rows}, images, {"images": len(coco["images"]), "images_with_region": dict(before)}


FRUITS = ("apple", "banana", "guava", "lime", "lemon", "orange", "pomegranate")


def fruitnet():
    base = EXTERNAL / "fruitnet" / "extracted"
    files = sorted(p for p in base.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png") and p.is_file())
    cmap = LABEL_MAP["datasets"]["fruitnet"]["classes"]
    parsed = []
    for p in files:
        parts = [s.lower() for s in p.relative_to(base).parts[:-1]]
        quality = next((q for q in ("Good", "Bad", "Mixed") if any(re.search(rf"\b{q.lower()}", s) for s in parts)), None)
        fruit = next((f for f in FRUITS if any(f in s for s in parts)), None)
        parsed.append((p, quality, fruit))
    unknown = [str(p.relative_to(base)) for p, q, f in parsed if q is None or f is None]
    if unknown:
        raise SystemExit(f"{len(unknown)} FruitNet files without a quality or fruit folder, e.g. {unknown[:3]}")
    keep = [(p, q, f) for p, q, f in parsed if cmap[q]["to"] != "ignore"]
    rgb = {}
    hashes = []
    for p, q, f in keep:
        im = Image.open(p).convert("RGB")
        im.thumbnail((256, 256))
        hashes.append(phash(im))
        rgb[p] = im.size
    pairs = near_pairs(hashes, NEAR)
    roots = groups_from_pairs(len(keep), pairs)
    rows, images = [], {}
    sizes = Counter()
    for (p, q, f), r in zip(keep, roots):
        with Image.open(p) as im:
            w, h = im.size
        sizes[f"{w}x{h}"] += 1
        group = f"fruitnet-{hashlib.sha1(str(keep[r][0].relative_to(base)).encode()).hexdigest()[:12]}"
        label = cmap[q]["to"]
        split = split_of(group)
        oid = hashlib.sha1(str(p.relative_to(base)).encode()).hexdigest()[:16]
        rows.append({"file": f"images/{split}/{label}/{f}-{oid}.png", "split": split, "label": label, "source_label": f"{q}/{f}", "label_basis": "source_class", "object_id": oid, "group": group, "source_file": p.relative_to(base).as_posix(), "source_size": f"{w}x{h}"})
        images[("fruitnet", f"{f}-{oid}.png")] = p
    before = {"files": Counter(f"{q}/{f}" for _, q, f in parsed), "grouping_pairs_within_hamming": len(pairs), "source_sizes": dict(sizes.most_common(5))}
    return {"fruitnet": rows}, images, before


def load_rgb(source):
    if isinstance(source, np.ndarray):
        return source
    with Image.open(source) as im:
        return np.asarray(im.convert("RGB"))


def duplicates(rows, name):
    base = PROCESSED / name

    @lru_cache(maxsize=4096)
    def vec(i):
        v = np.asarray(Image.open(base / rows[i]["file"]).convert("RGB"), dtype=np.float32).ravel()
        return (v - v.mean()) / (v.std() + 1e-6)

    exact, hashes, splits = {}, [], []
    for r in rows:
        a = np.asarray(Image.open(base / r["file"]).convert("RGB"))
        exact.setdefault(hashlib.sha1(a.tobytes()).hexdigest(), set()).add(r["split"])
        hashes.append(phash(Image.fromarray(a)))
        splits.append(r["split"])
    candidates = [(a, b, d) for a, b, d in near_pairs(hashes, NEAR) if splits[a] != splits[b]]
    scored = [(a, b, d, float(vec(a) @ vec(b) / vec(a).size)) for a, b, d in candidates]
    confirmed = [x for x in scored if x[3] >= CONFIRM]
    groups = {}
    for r in rows:
        groups.setdefault(r["group"], set()).add(r["split"])
    return {
        "exact_duplicate_images_in_two_splits": sum(1 for s in exact.values() if len(s) > 1),
        "phash_candidate_pairs_across_splits": len(candidates),
        "confirmed_near_duplicates_across_splits": len(confirmed),
        "rule": f"candidates: 64-bit DCT perceptual hash, Hamming distance <= {NEAR}; confirmed: Pearson correlation of the {SIZE}x{SIZE} RGB images >= {CONFIRM}",
        "highest_candidate_correlation": round(max((x[3] for x in scored), default=0.0), 4),
        "confirmed_examples": [[rows[a]["file"], rows[b]["file"], d, round(c, 4)] for a, b, d, c in confirmed[:5]],
        "groups_in_two_splits": sum(1 for s in groups.values() if len(s) > 1),
    }


def table(rows, labels):
    splits = ("train", "val", "test")
    c = Counter((r["split"], r["label"]) for r in rows)
    lines = ["| Split | " + " | ".join(labels) + " | Total |", "|---|" + "---|" * (len(labels) + 1)]
    for s in splits:
        lines.append(f"| {s} | " + " | ".join(str(c[(s, l)]) for l in labels) + f" | {sum(c[(s, l)] for l in labels)} |")
    lines.append("| all | " + " | ".join(str(sum(c[(s, l)] for s in splits)) for l in labels) + f" | {len(rows)} |")
    return lines


CARD_TEXT = {
    "potatoes": {
        "limitations": [
            "Real industrial sorting line, but only 50x50 px crops of single objects are published: no full frames, no video, so segmentation, tracking and counting cannot be trained or tested with it.",
            "Heavy duplication: 4,145 files hold 1,294 pixel-unique images and 757 objects once rotations and flips are counted; 224 of the 288 objects in the official test folders also appear in train or val. The official splits are not used here.",
            "`Damaged` mixes cut, rotten and diseased potatoes; it stays one merged label (`poor_or_rotten`).",
            "Potato, not cashew; the belt is grey-blue and close to potato colour.",
        ],
        "may": ["test how a classifier or a segmentation rule behaves on real belt imagery (background, lighting, motion blur, touching neighbours)", "pre-train or evaluate a good-versus-damaged head and a foreign-object detector for belts", "commercial use, with the attribution in SOURCE.md (CC BY 4.0)"],
        "may_not": ["be presented as cashew data or as cashew-on-belt data", "be used to report accuracy of the cashew product", "be evaluated on its official splits as if they were independent"],
    },
    "lemons": {
        "limitations": [
            "Lab rig with a dark background, one lemon per image; it is not a conveyor belt.",
            "The v1.0.0 COCO export has no image-level flags: `healthy` is derived (no defect region annotated) and `greening` cannot be used.",
            "`illness` has no definition in the README; it and `dark_style_remains` are kept as `poor_or_rotten`.",
            "Several photos (angles, positions) per lemon; all photos with the same fruit number are in one split. Two letters in the file names are undocumented and not used.",
            "Grouping by fruit number gives only 35 groups (5 to 197 photos each; 117 number+letter combinations, and the letters are undocumented). Split by group, validation and test hold 3 fruit numbers each and the test split has only 2 good photos: for any evaluation use cross-validation by fruit number, not this single split.",
            "Lemon, not cashew.",
        ],
        "may": ["study defect regions and background sensitivity on a uniform background", "build compositing material (the defect polygons are in the raw COCO file)", "commercial use, keeping the MIT copyright and permission notice (see SOURCE.md)"],
        "may_not": ["be presented as belt data or as cashew data", "be used to report accuracy of the cashew product"],
    },
    "fruitnet": {
        "limitations": [
            "Phone photos with varied backgrounds and lighting, indoor and outdoor; not a conveyor belt.",
            "`Bad` mixes all defect types and rot (`poor_or_rotten`); `Mixed` images are excluded.",
            "No capture-session or fruit identifiers: splits use groups of near-duplicate photos (perceptual hash), which removes repeated shots but cannot guarantee that two different photos of one fruit end up in the same split.",
            "Apple, banana, guava, lime, orange and pomegranate; guava is the only tropical fruit and none is cashew.",
            "Unbalanced: good pomegranate has 5,940 images, about five times every other class; many photos come in near-identical runs of three.",
            "The processed folders mix 256-px images with 564 full-resolution originals (381 at 3000x4000 and 183 at 8000x6000); all are resized to 128 px here.",
            "Most photos show 2 to 5 fruits of the same quality, and some show hands; a label describes the whole photo, not one fruit.",
        ],
        "may": ["test background sensitivity and pre-train generic good-versus-bad features", "commercial use, with the attribution in SOURCE.md (CC BY 4.0)"],
        "may_not": ["be presented as belt data or as cashew data", "be used to report accuracy of the cashew product"],
    },
}


def card(ds_id, sets, before, dup):
    m = META[ds_id]
    t = CARD_TEXT[ds_id]
    lines = [f"# Dataset card: {m['title']}", "", f"Source, licence, hashes and attribution: [data/external/{ds_id}/SOURCE.md](../../data/external/{ds_id}/SOURCE.md). Label mapping: [data/label_map.json](../../data/label_map.json). Produced by `python scripts/convert_external.py`.", "", f"- Setting: **{m['setting']}**", f"- Fruit: {m['fruit']}", f"- Licence: [{m['licence']}]({m['licence_url']}) ({m['commercial_use']})", f"- Processed images: {SIZE}x{SIZE} px RGB PNG, the classifier's input size, in `data/processed/<set>/images/<split>/<label>/`, with `manifest.csv`", "", "## Before mapping", "", "```json", json.dumps(before, ensure_ascii=False, indent=1, default=dict), "```", "", "## After mapping (counts of files on disk)", ""]
    for name, rows in sets.items():
        labels = [l for l in ORDER if any(r["label"] == l for r in rows)]
        lines += [f"### `{name}`", "", *table(rows, labels), ""]
        lines += ["Split by group (sha256 of the group id, 70/15/15). Duplicate check across splits:", "", "```json", json.dumps(dup[name], indent=1), "```", ""]
    lines += ["## Known limitations", "", *[f"- {x}" for x in t["limitations"]], "", "## How it may be used", "", *[f"- {x}" for x in t["may"]], "", "## How it may not be used", "", *[f"- {x}" for x in t["may_not"]], ""]
    (CARDS / f"{ds_id}.md").write_text("\n".join(lines), encoding="utf-8")


def write(name, rows, images):
    out = PROCESSED / name
    if out.exists():
        shutil.rmtree(out)
    for r in rows:
        save(load_rgb(images[(name, Path(r["file"]).name)]), out / r["file"])
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=["potatoes", "lemons", "fruitnet"])
    args = parser.parse_args()
    CARDS.mkdir(parents=True, exist_ok=True)
    report = {}
    for ds_id in args.only:
        sets, images, before = {"potatoes": potatoes, "lemons": lemons, "fruitnet": fruitnet}[ds_id]()
        dup = {}
        for name, rows in sets.items():
            write(name, rows, images)
            dup[name] = duplicates(rows, name)
            report[name] = {"rows": len(rows), "labels": dict(Counter(r["label"] for r in rows)), "duplicates": dup[name]}
            print(name, json.dumps(report[name]), flush=True)
        card(ds_id, sets, before, dup)
    path = PROCESSED / "conversion_report.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    path.write_text(json.dumps({**old, **report}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
