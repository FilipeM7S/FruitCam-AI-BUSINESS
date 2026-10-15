import argparse
import hashlib
import json
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler

from training import cashew_data as D
from training.train import build_model
from training.train_belt import MEAN, STD, ece, fit_temperature, logits_of, recalls, reject_threshold, report, transforms_for

ROOT = Path(__file__).resolve().parent.parent
DATA_SOURCE = "Drone-based Agricultural Dataset for Crop Yield Estimation, cashew parts: close-range drone photos of cashew trees in Ghana (1600x1300) and Uganda (640x480 copy), YOLO boxes with four fruit stages"


def subset(rows, split, sources=None, cap=None, seed=0):
    picked = [r for r in rows if r["split"] == split and (not sources or r["source"] in sources)]
    if cap:
        groups = {}
        for r in sorted(picked, key=lambda r: D.rank(f"{seed}:{r['key']}")):
            groups.setdefault((r["source"], r["label"]), []).append(r)
        picked = [r for group in groups.values() for r in group[:cap]]
    return picked


def items_for_report(rows):
    return [{"photo": f"{r['source']}:{r['photo']}", "label": D.CLASSES.index(r["label"]), "source": r["stage"]} for r in rows]


def source_report(probs, y, rows, threshold, args):
    present = set(y.tolist())
    if len(present) == len(D.CLASSES):
        return report(probs, y, items_for_report(rows), threshold, args.bootstrap, args.seed)
    pred = probs.argmax(1)
    recall = {D.CLASSES[c]: float((pred[y == c] == c).float().mean()) for c in sorted(present)}
    return {"n": int(len(y)), "photos": len({r["photo"] for r in rows}), "accuracy": float((pred == y).float().mean()), "balanced_accuracy": float(np.mean(list(recall.values()))), "recall": recall, "classes_missing_in_this_source": [c for i, c in enumerate(D.CLASSES) if i not in present]}


def deployed(result):
    if "with_reject" not in result:
        return result
    measured = result["with_reject"]
    return {**result, "field_photo_threshold": measured, "with_reject": {"threshold": None, "coverage": 0.0, "accuracy_on_accepted": None, "n_accepted": 0}}


def sampler_for(rows, size, seed):
    groups = Counter((r["source"], r["label"]) for r in rows)
    classes = Counter(r["label"] for r in rows)
    sources_in = {c: len({s for s, k in groups if k == c}) for c in classes}
    weights = torch.tensor([1.0 / (len(classes) * sources_in[r["label"]] * groups[(r["source"], r["label"])]) for r in rows], dtype=torch.double)
    return WeightedRandomSampler(weights, num_samples=size, replacement=True, generator=torch.Generator().manual_seed(seed))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(D.OUT))
    parser.add_argument("--out", default=str(ROOT / "models" / "belt_v3.pt"))
    parser.add_argument("--sources", nargs="*", default=None)
    parser.add_argument("--img-size", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--epoch-size", type=int, default=9000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--composite", type=float, default=0.5)
    parser.add_argument("--video-backgrounds", default=str(D.STORE / "video_backgrounds" / "train"))
    parser.add_argument("--video-share", type=float, default=0.5)
    parser.add_argument("--eval-cap", type=int, default=1500)
    parser.add_argument("--target-accuracy", type=float, default=0.95)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    start = time.perf_counter()
    rows = D.manifest(args.data)
    splits = {s: subset(rows, s, args.sources, None if s == "train" else args.eval_cap, args.seed) for s in ("train", "val", "test")}
    photos = {s: {(r["source"], r["photo"]) for r in v} for s, v in splits.items()}
    assert not (photos["train"] & photos["val"]) and not (photos["train"] & photos["test"]) and not (photos["val"] & photos["test"])
    counts = {s: dict(sorted(Counter(f"{r['source']}/{r['label']}" for r in v).items())) for s, v in splits.items()}
    print(f"crops: {json.dumps(counts)}; photos {({s: len(p) for s, p in photos.items()})}", flush=True)
    train_tf, plain = transforms_for(args.img_size)
    bank = [np.asarray(Image.open(path).convert("RGB")) for path in sorted(Path(args.video_backgrounds).glob("*.jpg"))] if args.video_share > 0 else []
    print(f"real video backgrounds for compositing: {len(bank)} pictures, used in {args.video_share:.0%} of the composites", flush=True)
    train = D.CropFiles(splits["train"], train_tf, args.data, args.composite, args.seed, bank=bank or None, bank_share=args.video_share)
    train_loader = DataLoader(train, batch_size=args.batch_size, sampler=sampler_for(splits["train"], args.epoch_size, args.seed))
    val_loader = DataLoader(D.CropFiles(splits["val"], plain, args.data), batch_size=256)
    test_loader = DataLoader(D.CropFiles(splits["test"], plain, args.data), batch_size=256)
    model = build_model(len(D.CLASSES), pretrained=True)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs * len(train_loader))
    best, best_state, history = -1.0, None, []
    for epoch in range(args.epochs):
        model.train()
        t0 = time.perf_counter()
        total, seen = 0.0, 0
        for x, y in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            scheduler.step()
            total += float(loss.detach()) * len(y)
            seen += len(y)
        logits, y = logits_of(model, val_loader)
        rec = recalls(logits.argmax(1), y, len(D.CLASSES))
        balanced = float(np.mean(rec))
        history.append({"epoch": epoch, "train_loss": total / seen, "val_balanced_accuracy": balanced, "val_recall": dict(zip(D.CLASSES, rec)), "seconds": time.perf_counter() - t0})
        print(f"epoch {epoch:2d} loss {total / seen:.4f} val balanced {balanced:.4f} recall {dict(zip(D.CLASSES, [round(r, 3) for r in rec]))} {time.perf_counter() - t0:.0f} s", flush=True)
        if balanced > best:
            best = balanced
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    val_logits, val_y = logits_of(model, val_loader)
    temperature = fit_temperature(val_logits, val_y)
    val_probs = torch.softmax(val_logits / temperature, 1)
    threshold = reject_threshold(val_probs, val_y, args.target_accuracy)
    test_logits, test_y = logits_of(model, test_loader)
    test_probs = torch.softmax(test_logits / temperature, 1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    stage_map = {stage: D.PRODUCT[stage] for stage in D.STAGES}
    torch.save({"model_state": model.state_dict(), "classes": D.CLASSES, "img_size": args.img_size, "temperature": temperature, "reject_below": None, "mean": MEAN, "std": STD, "version": out.stem, "class_map": stage_map}, out)
    by_source = {}
    for source in sorted({r["source"] for r in splits["test"]}):
        index = [i for i, r in enumerate(splits["test"]) if r["source"] == source]
        by_source[source] = source_report(test_probs[index], test_y[index], [splits["test"][i] for i in index], threshold, args)
    summary = json.loads((Path(args.data) / "summary.json").read_text(encoding="utf-8"))
    evaluation = {
        "model": {"file": out.name, "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "architecture": "MobileNetV3-Small (ImageNet pretrained)", "img_size": args.img_size, "classes": D.CLASSES, "temperature": temperature, "reject_below": None, "field_photo_threshold_for_target_accuracy": threshold},
        "data": {
            "source": DATA_SOURCE,
            "sources_used": sorted({r["source"] for r in splits["train"]}),
            "build": summary,
            "compositing": {"share": args.composite, "belts": list(D.TRAIN_BELTS), "held_out_belts_never_used_in_training": ["azul", "azul-claro"], "real_video_backgrounds": {"pictures": len(bank), "share_of_composites": args.video_share if bank else 0.0, "from": "potato sorting clips of the set usda_line_videos; the citrus and apple clips are held out for testing"}} if args.composite else None,
            "class_map": stage_map,
            "split": summary["rule"]["split"],
            "counts": {s: {c: sum(r["label"] == c for r in v) for c in D.CLASSES} for s, v in splits.items()},
            "counts_by_source": counts,
            "photos": {s: len(p) for s, p in photos.items()},
            "sampling": f"each epoch draws {args.epoch_size} training crops with equal weight for every class and, inside a class, for every source",
            "selection": "checkpoint with best validation balanced accuracy; temperature fitted on validation; test used once",
        },
        "training": {"epochs": args.epochs, "epoch_size": args.epoch_size, "batch_size": args.batch_size, "lr": args.lr, "seed": args.seed, "history": history, "seconds": time.perf_counter() - start},
        "validation": deployed(report(val_probs, val_y, items_for_report(splits["val"]), threshold, args.bootstrap, args.seed)),
        "test": deployed(report(test_probs, test_y, items_for_report(splits["test"]), threshold, args.bootstrap, args.seed)),
        "test_by_source": {source: deployed(result) for source, result in by_source.items()},
        "test_uncalibrated_ece": ece(torch.softmax(test_logits, 1), test_y),
        "test_predictions": {"y": test_y.tolist(), "p": [[round(float(v), 5) for v in row] for row in test_probs], "photo": [f"{r['source']}:{r['photo']}" for r in splits["test"]], "key": [r["key"] for r in splits["test"]]},
    }
    out.with_name(out.stem + "_eval.json").write_text(json.dumps(evaluation, indent=1) + "\n", encoding="utf-8")
    t = evaluation["test"]
    print(f"test n={t['n']} photos={t['photos']} acc={t['accuracy']:.3f} {t['accuracy_ci95_cluster_bootstrap']} balanced={t['balanced_accuracy']:.3f} baseline={t['majority_baseline_accuracy']:.3f} ece={t['ece']:.3f} T={temperature:.2f} threshold for {args.target_accuracy:.0%}: {threshold}")
    for source, r in by_source.items():
        print(f"  {source:10s} n={r['n']} balanced={r['balanced_accuracy']:.3f} acc={r['accuracy']:.3f}")
    print(json.dumps(t["per_class"], indent=1))


if __name__ == "__main__":
    main()
