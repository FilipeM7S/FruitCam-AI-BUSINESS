import argparse
import csv
import hashlib
import json
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from torch.utils.data import Dataset

from belt.composite import TRAIN_BELTS, composite, fruit_mask

ROOT = Path(__file__).resolve().parent.parent
STORE = Path(os.environ.get("FRUITCAM_DATA_STORE") or Path.home() / "FruitCamData")
OUT = STORE / "cashew_v3"
CLASSES = ["boa", "baixa_qualidade", "podre"]
PRODUCT = {"ripe": "boa", "premature": "baixa_qualidade", "unripe": "baixa_qualidade", "spoilt": "podre"}
STAGES = ("premature", "unripe", "ripe", "spoilt")
ORDER_PAPER = {2: "premature", 3: "unripe", 4: "ripe", 5: "spoilt"}
ORDER_ALPHA = {1: "premature", 2: "unripe", 3: "ripe", 4: "spoilt"}
TREE = {"paper": 0, "alpha": 5}
PHOTO_SIZED = 0.6
SOURCES = {
    "uganda": {"images": ROOT / "datasets" / "cashew" / "images", "labels": ROOT / "datasets" / "cashew" / "labels", "order": None},
    "ghana": {"images": STORE / "cashew_drone_full" / "members" / "ghana_cashew" / "Images", "labels": STORE / "cashew_drone_full" / "members" / "ghana_cashew" / "Labels", "order": "alpha"},
}
FIELDS = ["key", "source", "photo", "split", "stage", "label", "box_w", "box_h", "file", "mask", "inner"]


def rows_of(label_file):
    out = []
    for line in label_file.read_text(encoding="utf-8", errors="replace").splitlines():
        r = line.split()
        if len(r) >= 5:
            out.append((int(float(r[0])), float(r[1]), float(r[2]), float(r[3]), float(r[4])))
    return out


def label_order(rows):
    tree_first = any(c == TREE["paper"] and max(w, h) >= PHOTO_SIZED for c, _, _, w, h in rows)
    tree_last = any(c == TREE["alpha"] and max(w, h) >= PHOTO_SIZED for c, _, _, w, h in rows)
    if tree_first == tree_last:
        return None
    return "paper" if tree_first else "alpha"


def split_of(source, photo, seed=0):
    h = int(hashlib.sha256(f"{seed}:{source}:{photo}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if h < 0.7 else "val" if h < 0.85 else "test"


def rank(key):
    return hashlib.sha256(key.encode()).hexdigest()


def square(cx, cy, side, w, h):
    side = min(side, w, h)
    x0 = min(max(cx - side / 2, 0), w - side)
    y0 = min(max(cy - side / 2, 0), h - side)
    return round(x0), round(y0), round(x0 + side), round(y0 + side)


def picture(folder, stem):
    for ext in (".jpg", ".JPG", ".jpeg", ".png"):
        path = folder / f"{stem}{ext}"
        if path.exists():
            return path
    return None


def candidates(name, min_side, seed=0):
    source = SOURCES[name]
    found, skipped = [], Counter()
    for label_file in sorted(source["labels"].glob("*.txt")):
        rows = rows_of(label_file)
        order = source["order"] or label_order(rows)
        if order is None:
            skipped["label order not identifiable"] += 1
            continue
        image = picture(source["images"], label_file.stem)
        if image is None:
            skipped["photo not downloaded"] += 1
            continue
        stages = ORDER_PAPER if order == "paper" else ORDER_ALPHA
        tag = name if source["order"] else f"{name}_{'a' if order == 'paper' else 'b'}"
        for i, (c, cx, cy, w, h) in enumerate(rows):
            if c in stages:
                found.append({"source": tag, "photo": label_file.stem, "image": image, "index": i, "stage": stages[c], "box": (cx, cy, w, h), "split": split_of(tag, label_file.stem, seed)})
    return found, skipped


def cut_photo(job):
    image, items, out, margin, side = job
    out = Path(out)
    rows, methods = [], Counter()
    with Image.open(image) as im:
        rgb = im.convert("RGB")
    for it in items:
        w, h = it["size"]
        cx, cy, bw, bh = it["box"]
        box = square(cx * w, cy * h, max(bw * w, bh * h) * (1 + margin), w, h)
        crop = rgb.crop(box)
        scale = min(1.0, side / crop.width)
        if scale < 1:
            crop = crop.resize((side, side), Image.LANCZOS)
        inner = [round(v * scale, 1) for v in (cx * w - bw * w / 2 - box[0], cy * h - bh * h / 2 - box[1], cx * w + bw * w / 2 - box[0], cy * h + bh * h / 2 - box[1])]
        file = f"crops/{it['key']}.jpg"
        crop.save(out / file, "JPEG", quality=92)
        mask, method = fruit_mask(np.asarray(crop), inner)
        methods[method] += 1
        cv2.imwrite(str(out / f"crops/{it['key']}.png"), mask * 255)
        rows.append({"key": it["key"], "source": it["source"], "photo": it["photo"], "split": it["split"], "stage": it["stage"], "label": PRODUCT[it["stage"]], "box_w": round(bw * w), "box_h": round(bh * h), "file": file, "mask": f"crops/{it['key']}.png", "inner": json.dumps(inner)})
    return rows, methods


def build(out=OUT, min_side=24, margin=0.15, side=160, cap=6000, include=("uganda_b", "ghana"), seed=0, workers=6):
    out = Path(out)
    (out / "crops").mkdir(parents=True, exist_ok=True)
    found, skipped = [], Counter()
    for name in SOURCES:
        items, missing = candidates(name, min_side, seed)
        found += [it for it in items if it["source"] in include]
        skipped.update({f"{name}: {k}": v for k, v in missing.items()})
    by_photo, manifest, small, methods = {}, [], Counter(), Counter()
    for it in found:
        by_photo.setdefault((it["source"], it["image"]), []).append(it)
    chosen = {}
    for (source, image), items in sorted(by_photo.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        with Image.open(image) as im:
            w, h = im.size
        for it in items:
            cx, cy, bw, bh = it["box"]
            if min(bw * w, bh * h) < min_side:
                small[(source, it["stage"])] += 1
                continue
            it["size"] = (w, h)
            it["key"] = f"{source}__{it['photo']}__{it['index']}"
            chosen.setdefault((source, it["stage"], it["split"]), []).append(it)
    share = {"train": 0.7, "val": 0.15, "test": 0.15}
    keep = []
    for (source, stage, split), items in chosen.items():
        items.sort(key=lambda it: rank(it["key"]))
        keep += items[:max(1, int(cap * share[split]))]
    wanted = {}
    for it in keep:
        wanted.setdefault(str(it["image"]), []).append({k: it[k] for k in ("key", "source", "photo", "split", "stage", "box", "size")})
    jobs = [(image, items, str(out), margin, side) for image, items in sorted(wanted.items())]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for rows, counted in pool.map(cut_photo, jobs, chunksize=8):
            manifest += rows
            methods.update(counted)
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(manifest)
    summary = {
        "rule": {"min_box_side_px": min_side, "margin": margin, "crop_side_px": side, "cap_per_source_and_stage": cap, "sources": list(include), "split": "by source photo (sha256 of seed, source and file name), 70/15/15; no photo appears in two splits"},
        "label_orders": {"alpha": "flower, premature, unripe, ripe, spoilt, tree (ids 0 to 5)", "paper": "tree, flower, premature, unripe, ripe, spoilt (ids 0 to 5)"},
        "skipped_files": dict(skipped),
        "boxes_smaller_than_the_minimum": {f"{s}/{st}": n for (s, st), n in sorted(small.items())},
        "crops": {f"{s}/{st}/{sp}": len(v) for (s, st, sp), v in sorted(chosen.items())},
        "kept": dict(Counter(f"{r['source']}/{r['label']}/{r['split']}" for r in manifest)),
        "photos": {f"{s}/{sp}": len({r["photo"] for r in manifest if r["source"] == s and r["split"] == sp}) for s in sorted({r["source"] for r in manifest}) for sp in ("train", "val", "test")},
        "masks": dict(methods),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
    return summary


def manifest(out=OUT):
    with (Path(out) / "manifest.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


class CropFiles(Dataset):
    def __init__(self, rows, tf, root=OUT, composite_share=0.0, seed=0, palette=TRAIN_BELTS, bank=None, bank_share=0.5):
        self.rows = rows
        self.tf = tf
        self.root = Path(root)
        self.share = composite_share
        self.rng = np.random.default_rng(seed)
        self.palette = palette
        self.bank = bank
        self.bank_share = bank_share

    def __len__(self):
        return len(self.rows)

    def image(self, row):
        with Image.open(self.root / row["file"]) as im:
            return im.convert("RGB")

    def mask(self, row):
        return (cv2.imread(str(self.root / row["mask"]), cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8)

    def __getitem__(self, i):
        row = self.rows[i]
        image = self.image(row)
        if self.share and self.rng.random() < self.share:
            image = Image.fromarray(composite(np.asarray(image), self.mask(row), self.rng, self.palette, self.bank, self.bank_share)[0])
        return self.tf(image), CLASSES.index(row["label"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--include", nargs="+", default=["uganda_a", "uganda_b", "ghana"])
    parser.add_argument("--min-side", type=int, default=24)
    parser.add_argument("--cap", type=int, default=6000)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    started = time.time()
    summary = build(args.out, args.min_side, cap=args.cap, include=tuple(args.include), workers=args.workers)
    print(f"built in {time.time() - started:.0f} s")
    print(json.dumps({k: summary[k] for k in ("skipped_files", "kept", "photos", "masks", "boxes_smaller_than_the_minimum")}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
