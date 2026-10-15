import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import video_backgrounds
from belt.composite import composite
from belt.stats import wilson
from training import cashew_data as D
from training import ttst
from training.train_belt import cluster_bootstrap
from training.train_v3 import subset

OUT = ROOT / "docs" / "reports" / "ttst"
K = len(D.CLASSES)


def pasted(rows, files, bank, seed):
    rng = np.random.default_rng(seed)
    return [cv2.cvtColor(composite(np.asarray(files.image(r)), files.mask(r), rng, bank=bank, bank_share=1.0)[0], cv2.COLOR_RGB2BGR) for r in rows]


def plain(rows, files):
    return [cv2.cvtColor(np.asarray(files.image(r)), cv2.COLOR_RGB2BGR) for r in rows]


def labels_of(rows):
    return np.array([D.CLASSES.index(r["label"]) for r in rows])


def score(classifier, crops, rows, draws, seed):
    probs = np.concatenate([classifier.probs(crops[i:i + 128]) for i in range(0, len(crops), 128)])
    y, pred = labels_of(rows), probs.argmax(axis=1)
    photos = [f"{r['source']}:{r['photo']}" for r in rows]
    recalls = [float((pred[y == c] == c).mean()) for c in range(K)]
    _, ci = cluster_bootstrap(photos, (pred == y).astype(float), y, K, draws, seed)
    rotten = y == ttst.ROTTEN
    hit, good = int((pred[rotten] == ttst.ROTTEN).sum()), int((pred[rotten] == 0).sum())
    return {"n": int(len(y)), "photos": len(set(photos)), "balanced_accuracy": float(np.mean(recalls)), "balanced_accuracy_ci95": ci, "recall": dict(zip(D.CLASSES, recalls)), "rotten_recall": {"k": hit, "n": int(rotten.sum()), "ci95": wilson(hit, int(rotten.sum()))}, "rotten_called_good": {"k": good, "n": int(rotten.sum()), "ci95": wilson(good, int(rotten.sum()))}}


def paired(before, after, rows, draws, seed):
    y = labels_of(rows)
    photos = {}
    for i, r in enumerate(rows):
        photos.setdefault(f"{r['source']}:{r['photo']}", []).append(i)
    groups = [np.array(v) for v in photos.values()]
    rng = np.random.default_rng(seed)

    def balanced(pred, index):
        return np.mean([(pred[index][y[index] == c] == c).mean() for c in range(K) if (y[index] == c).any()])

    gains = []
    for _ in range(draws):
        index = np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))])
        gains.append(balanced(after, index) - balanced(before, index))
    return [float(v) for v in np.percentile(gains, [2.5, 97.5])]


def predictions(classifier, crops):
    return np.concatenate([classifier.probs(crops[i:i + 128]) for i in range(0, len(crops), 128)]).argmax(axis=1)


def fill(buffer, classifier, stream, rows, corrected, flipped, seed):
    rng = np.random.default_rng(seed)
    probs = np.concatenate([classifier.probs(stream[i:i + 128]) for i in range(0, len(stream), 128)])
    y = labels_of(rows)
    for i, r in enumerate(rows):
        buffer.offer(r["key"], stream[i], probs[i])
    wrong_pseudo = sum(v["label"] != y[i] for i, r in enumerate(rows) for v in [buffer.items.get(r["key"])] if v)
    for i in rng.choice(len(rows), int(corrected * len(rows)), replace=False):
        buffer.correct(rows[i]["key"], stream[i], y[i])
    turned = 0
    if flipped:
        keys = sorted(buffer.items)
        at = {r["key"]: i for i, r in enumerate(rows)}
        for key in rng.choice(keys, int(flipped * len(keys)), replace=False):
            true = int(y[at[key]])
            buffer.correct(key, buffer.items[key]["crop"], int(rng.choice([c for c in range(K) if c != true])))
            turned += 1
    held = [(v["label"], int(y[i])) for i, r in enumerate(rows) for v in [buffer.items.get(r["key"])] if v]
    return {"stream": len(rows), "accepted_as_pseudo_label": sum(v["origin"] == "pseudo" for v in buffer.items.values()), "refused_below_the_confidence_threshold": buffer.refused, "pseudo_labels_wrong_before_any_correction": int(wrong_pseudo), "operator_corrections": int(corrected * len(rows)), "labels_flipped_on_purpose": turned, "wrong_labels_in_the_buffer": sum(a != b for a, b in held), "buffer_size": len(held), "counts": buffer.counts()}


def case(name, args, data, corrected=0.0, flipped=0.0, seed=0):
    started = time.perf_counter()
    log = Path(args.out) / "updates.jsonl"
    adapter = ttst.Adapter(args.model, data["control"], log, lr=args.lr, steps=args.steps, max_update=args.max_update, min_per_class=args.min_per_class, tolerance=args.tolerance, seed=seed)
    before_target, before = data["before_target"], data["before"]
    buffer = ttst.Buffer(threshold=args.threshold, per_class=args.per_class)
    filled = fill(buffer, adapter.classifier, data["stream"], data["stream_rows"], corrected, flipped, seed)
    entry = adapter.step(buffer)
    after_target = predictions(adapter.classifier, data["target"])
    after = {"target": score(adapter.classifier, data["target"], data["test_rows"], args.bootstrap, seed), "source": score(adapter.classifier, data["source"], data["test_rows"], args.bootstrap, seed)}
    out = {"case": name, "seed": seed, "buffer": filled, "update": entry, "target_test_before": before["target"], "target_test_after": after["target"], "target_gain_ci95_paired_by_photo": paired(before_target, after_target, data["test_rows"], args.bootstrap, seed), "source_test_before": before["source"], "source_test_after": after["source"]}
    if adapter.refused_state is not None:
        adapter.classifier.model.load_state_dict(adapter.refused_state)
        refused = predictions(adapter.classifier, data["target"])
        out["target_test_if_the_update_had_been_kept"] = score(adapter.classifier, data["target"], data["test_rows"], args.bootstrap, seed)
        out["target_change_if_kept_ci95_paired_by_photo"] = paired(before_target, refused, data["test_rows"], args.bootstrap, seed)
    out["seconds"] = round(time.perf_counter() - started, 1)
    b, a = out["target_test_before"], out["target_test_after"]
    print(f"{name:28s} seed {seed}: buffer {filled['buffer_size']} ({filled['wrong_labels_in_the_buffer']} wrong) | control {entry.get('control_before', {}).get('balanced_accuracy', float('nan')):.3f} -> {entry.get('control_after', {}).get('balanced_accuracy', float('nan')):.3f} | {entry['status']} | target test {b['balanced_accuracy']:.3f} -> {a['balanced_accuracy']:.3f} (gain CI {out['target_gain_ci95_paired_by_photo'][0]:+.3f} to {out['target_gain_ci95_paired_by_photo'][1]:+.3f})" + (f" | if kept {out['target_test_if_the_update_had_been_kept']['balanced_accuracy']:.3f}" if adapter.refused_state is not None else "") + f" [{out['seconds']:.0f} s]", flush=True)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=str(ROOT / "models" / "belt_v3.pt"))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--stream-cap", type=int, default=400)
    parser.add_argument("--control-cap", type=int, default=200)
    parser.add_argument("--test-cap", type=int, default=800)
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument("--per-class", type=int, default=400)
    parser.add_argument("--min-per-class", type=int, default=30)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--max-update", type=float, default=0.05)
    parser.add_argument("--tolerance", type=float, default=0.005)
    parser.add_argument("--corrected", type=float, default=0.1)
    parser.add_argument("--flipped", type=float, default=0.3)
    parser.add_argument("--bootstrap", type=int, default=1000)
    args = parser.parse_args()
    os.environ[ttst.FLAG] = "1"
    started = time.perf_counter()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "updates.jsonl").write_text("", encoding="utf-8")
    sources = json.loads(Path(args.model).with_name(Path(args.model).stem + "_eval.json").read_text(encoding="utf-8"))["data"]["sources_used"]
    rows = D.manifest()
    files = D.CropFiles([], None)
    bank = video_backgrounds.bank("test")
    here, there = bank[0::2], bank[1::2]
    val = subset(rows, "val", sources)
    photos = sorted({f"{r['source']}:{r['photo']}" for r in val}, key=lambda p: D.rank(f"ttst:{p}"))
    first = set(photos[: len(photos) // 2])
    stream_rows = subset([r for r in val if f"{r['source']}:{r['photo']}" in first], "val", sources, args.stream_cap, 0)
    control_rows = subset([r for r in val if f"{r['source']}:{r['photo']}" not in first], "val", sources, args.control_cap, 0)
    test_rows = subset(rows, "test", sources, args.test_cap, 0)
    data = {
        "stream_rows": stream_rows,
        "stream": pasted(stream_rows, files, here, 1),
        "control": {"keys": [r["key"] for r in control_rows], "crops": pasted(control_rows, files, here, 2), "labels": labels_of(control_rows)},
        "test_rows": test_rows,
        "target": pasted(test_rows, files, there, 3),
        "source": plain(test_rows, files),
    }
    setup = {
        "what": "simulated domain shift: the classifier was trained on field photos; the target is the same fruit cut out and pasted on frames of real sorting-line video. Nothing here was measured on a real belt.",
        "model": Path(args.model).name,
        "flag": f"{ttst.FLAG}=1 set by this tool only",
        "stream_unlabelled_for_the_model": {"crops": len(stream_rows), "photos": len({(r['source'], r['photo']) for r in stream_rows}), "split": "validation photos, first half by hash", "per_class": {c: int((labels_of(stream_rows) == i).sum()) for i, c in enumerate(D.CLASSES)}},
        "control_never_trained_on": {"crops": len(control_rows), "photos": len({(r['source'], r['photo']) for r in control_rows}), "split": "validation photos, second half by hash", "per_class": {c: int((labels_of(control_rows) == i).sum()) for i, c in enumerate(D.CLASSES)}},
        "target_test": {"crops": len(test_rows), "photos": len({(r['source'], r['photo']) for r in test_rows}), "split": "test photos", "per_class": {c: int((labels_of(test_rows) == i).sum()) for i, c in enumerate(D.CLASSES)}},
        "photos_shared": {"stream_and_control": len({(r['source'], r['photo']) for r in stream_rows} & {(r['source'], r['photo']) for r in control_rows}), "stream_and_test": len({(r['source'], r['photo']) for r in stream_rows} & {(r['source'], r['photo']) for r in test_rows}), "control_and_test": len({(r['source'], r['photo']) for r in control_rows} & {(r['source'], r['photo']) for r in test_rows})},
        "background_pictures": {"stream_and_control": len(here), "target_test": len(there), "shared": 0, "from": "held-out citrus and apple clips; none was used to train the classifier"},
        "settings": {k: getattr(args, k) for k in ("threshold", "per_class", "min_per_class", "lr", "steps", "max_update", "tolerance", "corrected", "flipped", "bootstrap", "seeds")},
    }
    print(json.dumps({k: setup[k] for k in ("stream_unlabelled_for_the_model", "control_never_trained_on", "target_test", "photos_shared", "background_pictures")}, ensure_ascii=False), f"[prepared in {time.perf_counter() - started:.0f} s]", flush=True)
    start = ttst.CropClassifier(args.model)
    data["before_target"] = predictions(start, data["target"])
    data["before"] = {"target": score(start, data["target"], test_rows, args.bootstrap, 0), "source": score(start, data["source"], test_rows, args.bootstrap, 0)}
    print(f"before any update: target test balanced accuracy {data['before']['target']['balanced_accuracy']:.3f}, source test {data['before']['source']['balanced_accuracy']:.3f} [{time.perf_counter() - started:.0f} s]", flush=True)
    cases = []
    for seed in args.seeds:
        cases.append(case("pseudo-labels only", args, data, seed=seed))
        cases.append(case("with operator corrections", args, data, corrected=args.corrected, seed=seed))
        cases.append(case("labels flipped on purpose", args, data, flipped=args.flipped, seed=seed))
    result = {**setup, "cases": cases, "seconds": round(time.perf_counter() - started, 1)}
    (out / "ttst.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
