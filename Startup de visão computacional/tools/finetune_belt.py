import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from belt.dataset import read_manifest, split_by_batch
from train import build_model
from train_belt import CLASSES, MEAN, STD, Crops, fit_temperature, load_crops, logits_of, recalls, reject_threshold, report, transforms_for


def items_of(root, rows):
    return [{"photo": r["fruit"], "split": None, "label": CLASSES.index(r["label"]), "source": r["label"], "image": Image.open(Path(root) / r["file"]).convert("RGB")} for r in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "belt_data"))
    parser.add_argument("--init", default=str(ROOT / "models" / "belt_v2.pt"))
    parser.add_argument("--out", default=str(ROOT / "models" / "belt_ft.pt"))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--mix-field", action="store_true", help="also train on the field-photo training crops, to keep what the model already knows")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--target-accuracy", type=float, default=0.95)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    start = time.perf_counter()
    rows = read_manifest(args.data)
    if not rows:
        raise SystemExit(f"no manifest.csv in {args.data}; record trays first with: python manage.py record_tray <camera> --label <class> --batch <tray>")
    splits, info = split_by_batch(rows, args.seed)
    for name, part in splits.items():
        missing = [c for c in CLASSES if not any(r["label"] == c for r in part)]
        if missing and name != "val":
            raise SystemExit(f"{name} split has no {missing}; record more trays of those classes")
    ck = torch.load(args.init, map_location="cpu")
    if list(ck["classes"]) != CLASSES:
        raise SystemExit(f"{args.init} has classes {ck['classes']}, expected {CLASSES}")
    size = int(ck["img_size"])
    data = {s: items_of(args.data, part) for s, part in splits.items()}
    train_items = list(data["train"])
    if args.mix_field:
        train_items += [it for it in load_crops(ROOT / "images", ROOT / "Labels", 24, 0.15, 0) if it["split"] == "train"]
    train_tf, plain = transforms_for(size)
    loaders = {s: DataLoader(Crops(v, plain), batch_size=128) for s, v in data.items()}
    model = build_model(len(CLASSES), pretrained=False)
    model.load_state_dict(ck["model_state"])
    before_logits, test_y = logits_of(model, loaders["test"])
    before = report(torch.softmax(before_logits / ck["temperature"], 1), test_y, data["test"], ck.get("reject_below"), args.bootstrap, args.seed)
    print(f"before fine-tuning ({Path(args.init).name}) on test trays: acc {before['accuracy']:.3f} {before['accuracy_ci95_cluster_bootstrap']} balanced {before['balanced_accuracy']:.3f}", flush=True)
    counts = torch.tensor([sum(it["label"] == i for it in train_items) for i in range(len(CLASSES))], dtype=torch.float)
    criterion = nn.CrossEntropyLoss(weight=counts.sum() / (len(CLASSES) * counts.clamp(min=1)))
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    train_loader = DataLoader(Crops(train_items, train_tf), batch_size=args.batch_size, shuffle=True)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs * len(train_loader))
    best, state, history = -1.0, {k: v.clone() for k, v in model.state_dict().items()}, []
    for epoch in range(args.epochs):
        model.train()
        for x, y in train_loader:
            optimizer.zero_grad()
            criterion(model(x), y).backward()
            optimizer.step()
            scheduler.step()
        logits, y = logits_of(model, loaders["val"])
        balanced = float(np.nanmean(recalls(logits.argmax(1), y, len(CLASSES))))
        history.append({"epoch": epoch, "val_balanced_accuracy": balanced})
        print(f"epoch {epoch} val balanced {balanced:.3f}", flush=True)
        if balanced > best:
            best, state = balanced, {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(state)
    val_logits, val_y = logits_of(model, loaders["val"])
    temperature = fit_temperature(val_logits, val_y)
    reject_below = reject_threshold(torch.softmax(val_logits / temperature, 1), val_y, args.target_accuracy)
    test_logits, test_y = logits_of(model, loaders["test"])
    after = report(torch.softmax(test_logits / temperature, 1), test_y, data["test"], reject_below, args.bootstrap, args.seed)
    out = Path(args.out)
    torch.save({"model_state": model.state_dict(), "classes": CLASSES, "img_size": size, "temperature": temperature, "reject_below": reject_below, "mean": MEAN, "std": STD, "version": out.stem, "class_map": ck.get("class_map"), "fine_tuned_from": Path(args.init).name}, out)
    evaluation = {
        "model": {"file": out.name, "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "fine_tuned_from": Path(args.init).name, "temperature": temperature, "reject_below": reject_below},
        "data": {"root": str(args.data), "split": "by tray (batch): each class's trays are ranked by hash; first tray = test, second = validation when there are 3 or more", **info, "counts": {s: {c: sum(r["label"] == c for r in part) for c in CLASSES} for s, part in splits.items()}, "fruits": {s: len({r["fruit"] for r in part}) for s, part in splits.items()}, "mix_field": args.mix_field},
        "training": {"epochs": args.epochs, "lr": args.lr, "history": history, "seconds": round(time.perf_counter() - start)},
        "test_before": before,
        "test_after": after,
    }
    out.with_name(out.stem + "_eval.json").write_text(json.dumps(evaluation, indent=1) + "\n", encoding="utf-8")
    print(f"after fine-tuning on test trays: acc {after['accuracy']:.3f} {after['accuracy_ci95_cluster_bootstrap']} balanced {after['balanced_accuracy']:.3f}; review below {reject_below}: coverage {after['with_reject']['coverage']:.3f}", flush=True)


if __name__ == "__main__":
    main()
