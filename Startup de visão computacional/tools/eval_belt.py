import argparse
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from belt.classify import CropClassifier, ModelDecider
from belt.pipeline import BeltPipeline
from belt.simulate import SimulatedBelt
from belt.stats import wilson
from train_belt import attach_masks, load_crops, tree_as_five

CLASSES = ["boa", "baixa_qualidade", "podre"]
MINUTES = 8
SEED = 11


def test_pool(min_side=16, masked=True):
    items = [it for it in load_crops(ROOT / "images", ROOT / "Labels", min_side, 0.15, 0, tree_as_five(ROOT / "Labels")) if it["split"] == "test"]
    if masked:
        attach_masks(items)
    pool = {c: [] for c in CLASSES}
    for it in items:
        crop = cv2.cvtColor(np.asarray(it["image"]), cv2.COLOR_RGB2BGR)
        pool[CLASSES[it["label"]]].append((crop, it["mask"]) if masked else crop)
    return pool, {c: len(v) for c, v in pool.items()}, len({it["photo"] for it in items})


def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    confusion = [[int(((y == i) & (p == j)).sum()) for j in range(3)] for i in range(3)]
    recall = [confusion[i][i] / max(sum(confusion[i]), 1) for i in range(3)]
    k = int((y == p).sum())
    return {"n": int(len(y)), "accuracy": k / len(y), "accuracy_ci95": wilson(k, len(y)), "balanced_accuracy": float(np.mean(recall)), "recall": dict(zip(CLASSES, recall)), "confusion": confusion}


def simulate(classifier, pool, seed=SEED, minutes=MINUTES):
    belt = SimulatedBelt(rate_per_s=2.0, mix=(1, 1, 1), seed=seed, crops=pool)
    decider = ModelDecider(classifier)
    truth_of = {}

    def decide(track):
        fruit = belt.truth_at(track["cx"], track["cy"])
        result = decider(track)
        first = classifier.probs(track["views"][:1])[0] if track["views"] else None
        truth_of[track["id"]] = (fruit, first)
        return result

    pipe = BeltPipeline(decide, belt.px_per_mm, belt.width, rows=(belt.top, belt.bottom))
    frames = int(minutes * 60 * belt.fps)
    passages = []
    for _ in range(frames):
        t, frame = belt.read()
        passages += pipe.process(t, frame)[0]
    end_t = (frames - 1) / belt.fps
    matched = [(p, *truth_of[p["track_id"]]) for p in passages]
    ids = [f["id"] for _, f, _ in matched if f is not None]
    y, multi, single, sizes = [], [], [], []
    for p, fruit, first in matched:
        if fruit is None:
            continue
        y.append(CLASSES.index(fruit["label"]))
        multi.append(CLASSES.index(p["label"]))
        single.append(int(first.argmax()) if first is not None else CLASSES.index(p["label"]))
        if p["size_mm"]:
            sizes.append(p["size_mm"] / (2 * math.sqrt(fruit["area_mm2"] / math.pi)))
    confident = [(yy, mm) for (p, fruit, _), yy, mm in zip([m for m in matched if m[1] is not None], y, multi) if not p["needs_review"]]
    expected = belt.next_id - sum(1 for f in belt.fruits if f["x"] < pipe.line_x)
    return {
        "fps": belt.fps,
        "counting": {"fruits_that_crossed_the_line": int(expected), "counted": len(passages), "matched_to_a_true_fruit": len(ids), "distinct_true_fruits": len(set(ids)), "double_counts": len(ids) - len(set(ids))},
        "multi_view": metrics(y, multi),
        "single_view": metrics(y, single),
        "with_review": {"threshold": classifier.reject_below, "coverage": len(confident) / max(len(y), 1), "accuracy_on_decided": float(np.mean([a == b for a, b in confident])) if confident else None, "n_decided": len(confident)},
        "views_per_fruit": float(np.mean([p["views"] for p in passages])) if passages else 0,
        "size_ratio_median": float(np.median(sizes)) if sizes else None,
        "size_ratio_p05_p95": [float(np.percentile(sizes, 5)), float(np.percentile(sizes, 95))] if sizes else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=str(ROOT / "models" / "belt_v2.pt"))
    parser.add_argument("--min-side", type=int, default=16)
    parser.add_argument("--discs", action="store_true", help="paste each crop as a disc with its leaves (the old setup) instead of the fruit mask")
    args = parser.parse_args()
    start = time.perf_counter()
    pool, pool_sizes, photos = test_pool(args.min_side, not args.discs)
    classifier = CropClassifier(args.model)
    result = {
        "setup": {
            "what": f"simulated belt carrying real held-out TEST fruit (photo-disjoint from training; label files with the paper's class numbering only), {'pasted as discs with their leaves' if args.discs else 'cut out with their masks, no leaves'}, processed by the real camera pipeline and models/{Path(args.model).name}",
            "model": Path(args.model).stem,
            "minutes_simulated": MINUTES,
            "rate_per_s": 2.0,
            "class_mix": "1:1:1",
            "test_crops": pool_sizes,
            "test_photos": photos,
            "seed": SEED,
            "note": "each fruit keeps one fixed image while it moves (no rotation or lighting change), so the extra views add little information here",
        },
        **simulate(classifier, pool),
        "seconds": round(time.perf_counter() - start, 1),
    }
    out = ROOT / "figures" / "data" / "belt_eval.json"
    out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "setup"}, indent=1))


if __name__ == "__main__":
    main()
