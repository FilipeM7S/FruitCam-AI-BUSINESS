import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from adapt_bn import adapt
from belt.classify import CropClassifier
from belt.composite import HELD_OUT_BELTS, composite
from belt.pipeline import BeltPipeline
from belt.simulate import SimulatedBelt
from eval_belt import CLASSES, simulate
from train_belt import attach_masks, cluster_bootstrap, load_crops, tree_as_five, wilson

TEST_SEED, ADAPT_SEED = 11, 23


def bgr(it):
    return cv2.cvtColor(np.asarray(it["image"]), cv2.COLOR_RGB2BGR)


def pool_of(items, split, masked):
    pool = {c: [] for c in CLASSES}
    for it in items:
        if it["split"] == split:
            pool[CLASSES[it["label"]]].append((bgr(it), it["mask"]) if masked else bgr(it))
    return pool


def composites(items, split, seed):
    rng = np.random.default_rng(seed)
    return [(it, composite(np.asarray(it["image"]), it["mask"], rng, HELD_OUT_BELTS)[0]) for it in items if it["split"] == split]


def score(classifier, rows, draws):
    probs = np.concatenate([classifier.probs([cv2.cvtColor(img, cv2.COLOR_RGB2BGR) for _, img in rows[i:i + 256]]) for i in range(0, len(rows), 256)])
    y = np.array([it["label"] for it, _ in rows])
    pred = probs.argmax(1)
    correct = (pred == y).astype(float)
    acc_ci, bal_ci = cluster_bootstrap([it["photo"] for it, _ in rows], correct, y, len(CLASSES), draws, 0)
    recall = [float(correct[y == c].mean()) for c in range(len(CLASSES))]
    conf = probs.max(1)
    keep = conf >= classifier.reject_below if classifier.reject_below is not None else np.zeros(len(y), bool)
    rotten, good = CLASSES.index("podre"), CLASSES.index("boa")
    k = int(((y == rotten) & (pred == good)).sum())
    return {
        "n": int(len(y)),
        "accuracy": float(correct.mean()),
        "accuracy_ci95_photo_bootstrap": acc_ci,
        "balanced_accuracy": float(np.mean(recall)),
        "balanced_accuracy_ci95_photo_bootstrap": bal_ci,
        "recall": dict(zip(CLASSES, recall)),
        "rotten_predicted_good": {"k": k, "n": int((y == rotten).sum()), "rate_ci95": wilson(k, int((y == rotten).sum()))},
        "with_review": {"threshold": classifier.reject_below, "coverage": float(keep.mean()), "accuracy_on_decided": float(correct[keep].mean()) if keep.any() else None},
    }


def belt_views(pool, seed, minutes):
    belt = SimulatedBelt(rate_per_s=2.0, mix=(1, 1, 1), seed=seed, crops=pool)
    views = []

    def keep(track):
        views.extend(Image.fromarray(cv2.cvtColor(v, cv2.COLOR_BGR2RGB)) for v in track["views"])
        return {"label": "indefinido", "confidence": None, "views": len(track["views"]), "size_mm": None, "needs_review": True}

    pipe = BeltPipeline(keep, belt.px_per_mm, belt.width, rows=(belt.top, belt.bottom))
    for _ in range(int(minutes * 60 * belt.fps)):
        t, frame = belt.read()
        pipe.process(t, frame)
    return views


def adapted(path, images):
    classifier = CropClassifier(path)
    adapt(classifier.model, images, classifier.size)
    classifier.model.eval()
    return classifier


def short(sim):
    return {"counted": sim["counting"]["counted"], "multi_view": {k: sim["multi_view"][k] for k in ("n", "accuracy", "accuracy_ci95", "balanced_accuracy", "recall")}, "with_review": sim["with_review"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["models/belt_v1.pt", "models/belt_v2_clean.pt", "models/belt_v2.pt"])
    parser.add_argument("--adabn", nargs="+", default=["belt_v1", "belt_v2"])
    parser.add_argument("--min-side", type=int, default=16)
    parser.add_argument("--minutes", type=float, default=8)
    parser.add_argument("--adapt-minutes", type=float, default=4)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--out", default=str(ROOT / "models" / "compare_models.json"))
    args = parser.parse_args()
    start = time.perf_counter()
    excluded = tree_as_five(ROOT / "Labels")
    items = [it for it in load_crops(ROOT / "images", ROOT / "Labels", args.min_side, 0.15, 0, excluded) if it["split"] in ("val", "test")]
    masks = attach_masks(items)
    field = [(it, np.asarray(it["image"])) for it in items if it["split"] == "test"]
    field_24 = [(it, img) for it, img in field if min(it["inner"][2] - it["inner"][0], it["inner"][3] - it["inner"][1]) >= 24]
    blue_test = composites(items, "test", 101)
    blue_val = [Image.fromarray(img) for _, img in composites(items, "val", 202)]
    masked_test = pool_of(items, "test", True)
    circle_test = pool_of(items, "test", False)
    sim_val = belt_views(pool_of(items, "val", True), ADAPT_SEED, args.adapt_minutes)
    print(f"masks {masks}; blue test {len(blue_test)}, blue val {len(blue_val)}, unlabelled belt views from validation fruit {len(sim_val)}; {time.perf_counter() - start:.0f} s", flush=True)
    results = {}
    for path in args.models:
        path = ROOT / path
        name = path.stem
        base = CropClassifier(path)
        results[name] = {
            "field_photo_test": score(base, field, args.bootstrap),
            "field_photo_test_boxes_24px_or_more": score(base, field_24, args.bootstrap),
            "held_out_blue_belt_composites": score(base, blue_test, args.bootstrap),
            "simulated_belt_masked_fruit": short(simulate(base, masked_test, TEST_SEED, args.minutes)),
            "simulated_belt_old_disc_crops": short(simulate(base, circle_test, TEST_SEED, args.minutes)),
        }
        print(name, json.dumps({k: (v.get("accuracy") or v.get("multi_view", {}).get("accuracy")) for k, v in results[name].items()}), f"{time.perf_counter() - start:.0f} s", flush=True)
        if name not in args.adabn:
            continue
        results[name + "+adabn"] = {
            "held_out_blue_belt_composites": score(adapted(path, blue_val), blue_test, args.bootstrap),
            "simulated_belt_masked_fruit": short(simulate(adapted(path, sim_val), masked_test, TEST_SEED, args.minutes)),
        }
        print(name + "+adabn", json.dumps({k: (v.get("accuracy") or v.get("multi_view", {}).get("accuracy")) for k, v in results[name + "+adabn"].items()}), f"{time.perf_counter() - start:.0f} s", flush=True)
    out = {
        "setup": {
            "test_fruit": f"the same held-out TEST crops for every model: label files with the paper's class numbering only ({len(excluded)} files that number 'tree' as 5 are excluded), boxes with short side >= {args.min_side} px, split by source photo (never used in training or validation of belt_v2*; belt_v1 was trained on the same photo split but with the excluded files included)",
            "test_counts": {c: sum(1 for it, _ in field if CLASSES[it["label"]] == c) for c in CLASSES},
            "test_photos": len({it["photo"] for it, _ in field}),
            "field_photo_test": "each crop as cut from the field photo (leaves around the fruit), scored here for every model",
            "held_out_blue_belt_composites": f"each test crop cut out with its GrabCut mask and pasted once onto a synthetic belt in colours never used in training ({', '.join(HELD_OUT_BELTS)}), fixed seed",
            "simulated_belt_masked_fruit": f"end-to-end camera pipeline (segment, track, count, classify) on the simulated belt for {args.minutes:g} min; real test fruit pasted with their masks, so no leaves; seed {TEST_SEED}",
            "simulated_belt_old_disc_crops": "same, but fruit pasted as discs that keep leaves around the fruit (the setup of the earlier 59.6% result)",
            "adabn": f"batch-norm statistics recomputed on unlabelled crops of VALIDATION fruit in the same setting (blue composites, or {args.adapt_minutes:g} min of simulated belt, seed {ADAPT_SEED}); temperature and review threshold unchanged",
            "masks": masks,
            "caveat": "all belt numbers are synthetic settings built from real fruit images; none is a measurement on a real cashew belt",
        },
        "results": results,
        "seconds": round(time.perf_counter() - start),
    }
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
