import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import video_backgrounds
from belt.classify import CropClassifier
from belt.composite import HELD_OUT_BELTS, composite
from training import cashew_data as D
from training.train_belt import cluster_bootstrap
from training.train_v3 import subset

K = len(D.CLASSES)


def probs_of(classifier, images, batch=128):
    out = []
    for i in range(0, len(images), batch):
        out.append(classifier.probs([cv2.cvtColor(im, cv2.COLOR_RGB2BGR) for im in images[i:i + batch]]))
    return np.concatenate(out) if out else np.zeros((0, K), np.float32)


def score(pred, y, photos=None, draws=0, seed=0):
    recall = {D.CLASSES[c]: float((pred[y == c] == c).mean()) for c in range(K) if (y == c).any()}
    out = {
        "n": int(len(y)),
        "accuracy": float((pred == y).mean()),
        "balanced_accuracy": float(np.mean(list(recall.values()))),
        "recall": recall,
        "confusion": [[int(((y == i) & (pred == j)).sum()) for j in range(K)] for i in range(K)],
        "rotten_called_good": float((pred[y == 2] == 0).mean()) if (y == 2).any() else None,
    }
    if photos is not None and draws and len(recall) == K:
        acc, bal = cluster_bootstrap(photos, (pred == y).astype(float), y, K, draws, seed)
        out["accuracy_ci95"] = acc
        out["balanced_accuracy_ci95"] = bal
        out["photos"] = len(set(photos))
    return out


def composites(images, masks, seed, palette=None, bank=None):
    rng = np.random.default_rng(seed)
    if bank:
        return [composite(im, m, rng, bank=bank, bank_share=1.0)[0] for im, m in zip(images, masks)]
    return [composite(im, m, rng, palette)[0] for im, m in zip(images, masks)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["models/belt_v2.pt", "models/belt_v3.pt"])
    parser.add_argument("--data", default=str(D.OUT))
    parser.add_argument("--eval-cap", type=int, default=1500)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=str(ROOT / "models" / "compare_v3.json"))
    args = parser.parse_args()
    started = time.perf_counter()
    rows = D.manifest(args.data)
    files = D.CropFiles(rows, None, args.data)
    test = subset(rows, "test", ("ghana", "uganda_b"), args.eval_cap, args.seed)
    old_eval = json.loads((ROOT / "models" / "belt_v2_eval.json").read_text(encoding="utf-8"))
    old_photos = set(old_eval["test_predictions"]["photo"])
    legacy = [r for r in rows if r["source"] == "uganda_a" and r["photo"] in old_photos]
    load = lambda picked: ([np.asarray(files.image(r)) for r in picked], [files.mask(r) for r in picked], np.array([D.CLASSES.index(r["label"]) for r in picked]), [f"{r['source']}:{r['photo']}" for r in picked])
    images, masks, y, photos = load(test)
    legacy_images, _, legacy_y, legacy_photos = load(legacy)
    bank = video_backgrounds.bank("test")
    views = {
        "field_photo_test": images,
        "held_out_blue_belts": composites(images, masks, args.seed + 1, HELD_OUT_BELTS),
        "held_out_real_video_backgrounds": composites(images, masks, args.seed + 2, bank=bank),
    }
    print(f"test crops {len(test)} from {len(set(photos))} photos; legacy crops {len(legacy)} from {len(set(legacy_photos))} photos; real video backgrounds for testing: {len(bank)} pictures; prepared in {time.perf_counter() - started:.0f} s", flush=True)
    report = {"test": {"crops": len(test), "photos": len(set(photos)), "by_source_and_class": {}, "rule": f"photos held out by hash; at most {args.eval_cap} crops per source and class"}, "legacy_test": {"crops": len(legacy), "photos": len(set(legacy_photos)), "rule": "crops of at least 24 px from the photos that were the test set of belt_v2 (first Uganda label batch, class ids read in the order given in the paper); neither model was trained on these photos"}, "real_video_backgrounds": {"pictures": len(bank), "from": "citrus packing clip of the set usda_line_videos and the clip of the set apple_grading_video; never used in training"}, "models": {}}
    for r in test:
        key = f"{r['source']}/{r['label']}"
        report["test"]["by_source_and_class"][key] = report["test"]["by_source_and_class"].get(key, 0) + 1
    for path in args.models:
        classifier = CropClassifier(ROOT / path)
        entry = {}
        plain = None
        for name, pictures in views.items():
            pred = probs_of(classifier, pictures).argmax(1)
            entry[name] = score(pred, y, photos, args.bootstrap, args.seed)
            if plain is None:
                plain = pred
                for source in ("ghana", "uganda_b"):
                    index = np.array([r["source"] == source for r in test])
                    entry[f"{name}_{source}"] = score(pred[index], y[index])
            else:
                entry[name]["same_answer_as_on_the_plain_crop"] = float((pred == plain).mean())
        entry["legacy_first_batch_test"] = score(probs_of(classifier, legacy_images).argmax(1), legacy_y, legacy_photos, args.bootstrap, args.seed)
        report["models"][classifier.version] = entry
        line = "  ".join(f"{name} {entry[name]['balanced_accuracy']:.3f}" for name in (*views, "legacy_first_batch_test"))
        print(f"{classifier.version:12s} balanced accuracy: {line}  | same answer on blue belts {entry['held_out_blue_belts']['same_answer_as_on_the_plain_crop']:.3f}, on real video backgrounds {entry['held_out_real_video_backgrounds']['same_answer_as_on_the_plain_crop']:.3f}  [{time.perf_counter() - started:.0f} s]", flush=True)
    Path(args.out).write_text(json.dumps(report, indent=1) + chr(10), encoding="utf-8")


if __name__ == "__main__":
    main()
