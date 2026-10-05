import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

from belt.composite import TRAIN_BELTS, composite, fruit_mask
from train import build_model

ROOT = Path(__file__).resolve().parent
MASK_CACHE = ROOT / "data_cache" / "fruit_masks.npz"
DATA_SOURCE = "Coffee and Cashew Nut Dataset, cashew part (Makerere University; Nakatumba-Nabende et al., Mendeley Data, doi:10.17632/r46c6bpfpf.1, CC BY 4.0): 3,098 field photos of cashew on trees, 640x480, YOLO boxes"
CLASSES = ["boa", "baixa_qualidade", "podre"]
SOURCE = {4: "boa", 2: "baixa_qualidade", 3: "baixa_qualidade", 5: "podre"}
SOURCE_NAMES = {2: "premature", 3: "unripe", 4: "ripe", 5: "spoilt"}
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]
Z = 1.959964


def split_of(stem, seed):
    h = int(hashlib.sha256(f"{seed}:{stem}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if h < 0.7 else "val" if h < 0.85 else "test"


def square(cx, cy, side, w, h):
    side = min(side, w, h)
    x0 = min(max(cx - side / 2, 0), w - side)
    y0 = min(max(cy - side / 2, 0), h - side)
    return round(x0), round(y0), round(x0 + side), round(y0 + side)


def tree_as_five(labels):
    out = set()
    for label_file in sorted(Path(labels).glob("*.txt")):
        rows = [r.split() for r in label_file.read_text().splitlines() if r.strip()]
        if any(int(r[0]) == 5 and max(float(r[3]), float(r[4])) >= 0.6 for r in rows):
            out.add(label_file.stem)
    return out


def load_crops(images, labels, min_side, margin, seed, exclude=()):
    items = []
    for label_file in sorted(labels.glob("*.txt")):
        if label_file.stem in exclude:
            continue
        image_path = images / f"{label_file.stem}.jpg"
        rows = [r.split() for r in label_file.read_text().splitlines() if r.strip()]
        rows = [r for r in rows if int(r[0]) in SOURCE]
        if not rows or not image_path.exists():
            continue
        image = Image.open(image_path).convert("RGB")
        w, h = image.size
        split = split_of(label_file.stem, seed)
        for i, r in enumerate(rows):
            cx, cy, bw, bh = (float(v) for v in r[1:5])
            if min(bw * w, bh * h) < min_side:
                continue
            box = square(cx * w, cy * h, max(bw * w, bh * h) * (1 + margin), w, h)
            inner = (cx * w - bw * w / 2 - box[0], cy * h - bh * h / 2 - box[1], cx * w + bw * w / 2 - box[0], cy * h + bh * h / 2 - box[1])
            items.append({"photo": label_file.stem, "key": f"{label_file.stem}:{i}", "split": split, "label": CLASSES.index(SOURCE[int(r[0])]), "source": SOURCE_NAMES[int(r[0])], "image": image.crop(box), "inner": inner})
    return items


def attach_masks(items, cache=MASK_CACHE):
    stored = dict(np.load(cache)) if cache.exists() else {}
    methods = {}
    for it in items:
        name = it["key"].replace(":", "__")
        if name not in stored:
            mask, method = fruit_mask(np.asarray(it["image"]), it["inner"])
            stored[name] = mask
            stored[name + "__method"] = np.array(method == "grabcut")
        it["mask"] = stored[name]
        it["mask_method"] = "grabcut" if bool(stored[name + "__method"]) else "ellipse"
        methods[it["mask_method"]] = methods.get(it["mask_method"], 0) + 1
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **stored)
    return methods


class Crops(Dataset):
    def __init__(self, items, tf, composite_share=0.0, seed=0, palette=TRAIN_BELTS):
        self.items = items
        self.tf = tf
        self.share = composite_share
        self.rng = np.random.default_rng(seed)
        self.palette = palette

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        it = self.items[i]
        image = it["image"]
        if self.share and self.rng.random() < self.share:
            image = Image.fromarray(composite(np.asarray(image), it["mask"], self.rng, self.palette)[0])
        return self.tf(image), it["label"]


def transforms_for(size):
    train = transforms.Compose([
        transforms.RandomResizedCrop(size, scale=(0.75, 1.0), ratio=(0.85, 1.18)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.RandomApply([transforms.RandomRotation(180)], p=0.5),
        transforms.ColorJitter(brightness=0.25, contrast=0.2, saturation=0.15),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    plain = transforms.Compose([transforms.Resize((size, size)), transforms.ToTensor(), transforms.Normalize(MEAN, STD)])
    return train, plain


@torch.no_grad()
def logits_of(model, loader):
    model.eval()
    out, ys = [], []
    for x, y in loader:
        out.append(model(x))
        ys.append(y)
    return torch.cat(out), torch.cat(ys)


def recalls(pred, y, k):
    return [float((pred[y == c] == c).float().mean()) if (y == c).any() else float("nan") for c in range(k)]


def fit_temperature(logits, y):
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=200)
    nll = nn.CrossEntropyLoss()

    def closure():
        opt.zero_grad()
        loss = nll(logits / log_t.exp(), y)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp())


def wilson(k, n):
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    centre = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return [centre - half, centre + half]


def ece(probs, y, bins=15):
    conf, pred = probs.max(1)
    edges = torch.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += float(m.float().mean()) * abs(float((pred[m] == y[m]).float().mean()) - float(conf[m].mean()))
    return total


def reject_threshold(probs, y, target):
    conf, pred = probs.max(1)
    for t in np.round(np.arange(0.34, 0.995, 0.01), 2):
        keep = conf >= t
        if keep.sum() >= 30 and float((pred[keep] == y[keep]).float().mean()) >= target:
            return float(t)
    return None


def cluster_bootstrap(photos, correct, y, k, draws, seed):
    rng = np.random.default_rng(seed)
    groups = {}
    for i, p in enumerate(photos):
        groups.setdefault(p, []).append(i)
    keys = list(groups)
    acc, bal = [], []
    for _ in range(draws):
        idx = np.concatenate([groups[keys[j]] for j in rng.integers(0, len(keys), len(keys))])
        acc.append(correct[idx].mean())
        per = [correct[idx][y[idx] == c].mean() for c in range(k) if (y[idx] == c).any()]
        bal.append(np.mean(per))
    return [float(np.percentile(acc, 2.5)), float(np.percentile(acc, 97.5))], [float(np.percentile(bal, 2.5)), float(np.percentile(bal, 97.5))]


def report(probs, y, items, reject_below, draws, seed):
    k = len(CLASSES)
    pred = probs.argmax(1)
    yn, pn = y.numpy(), pred.numpy()
    correct = (yn == pn).astype(float)
    confusion = [[int(((yn == i) & (pn == j)).sum()) for j in range(k)] for i in range(k)]
    per_class = {}
    for c, name in enumerate(CLASSES):
        tp = confusion[c][c]
        support = sum(confusion[c])
        predicted = sum(confusion[i][c] for i in range(k))
        per_class[name] = {"support": support, "recall": tp / support if support else None, "recall_ci95": wilson(tp, support), "precision": tp / predicted if predicted else None, "precision_ci95": wilson(tp, predicted)}
    acc_ci, bal_ci = cluster_bootstrap([it["photo"] for it in items], correct, yn, k, draws, seed)
    majority = max(sum(r) for r in confusion) / len(yn)
    conf = probs.max(1).values.numpy()
    keep = conf >= reject_below if reject_below is not None else np.zeros_like(conf, dtype=bool)
    sources = {}
    for name in sorted({it["source"] for it in items}):
        m = np.array([it["source"] == name for it in items])
        sources[name] = {"n": int(m.sum()), "predicted": {CLASSES[c]: int((pn[m] == c).sum()) for c in range(k)}}
    rotten, good = CLASSES.index("podre"), CLASSES.index("boa")
    return {
        "n": int(len(yn)),
        "photos": len({it["photo"] for it in items}),
        "accuracy": float(correct.mean()),
        "accuracy_ci95_cluster_bootstrap": acc_ci,
        "balanced_accuracy": float(np.mean([per_class[c]["recall"] for c in CLASSES])),
        "balanced_accuracy_ci95_cluster_bootstrap": bal_ci,
        "majority_baseline_accuracy": majority,
        "confusion": confusion,
        "per_class": per_class,
        "per_source_label": sources,
        "rotten_predicted_good": {"k": confusion[rotten][good], "n": sum(confusion[rotten]), "rate_ci95": wilson(confusion[rotten][good], sum(confusion[rotten]))},
        "ece": ece(probs, y),
        "with_reject": {"threshold": reject_below, "coverage": float(keep.mean()), "accuracy_on_accepted": float(correct[keep].mean()) if keep.any() else None, "n_accepted": int(keep.sum())},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", default=str(ROOT / "images"))
    parser.add_argument("--labels", default=str(ROOT / "Labels"))
    parser.add_argument("--out", default=str(ROOT / "models" / "belt_v2.pt"))
    parser.add_argument("--img-size", type=int, default=128)
    parser.add_argument("--min-side", type=int, default=24)
    parser.add_argument("--margin", type=float, default=0.15)
    parser.add_argument("--epochs", type=int, default=14)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--target-accuracy", type=float, default=0.95)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--composite", type=float, default=0.0, help="share of training crops pasted (fruit mask only) onto a random synthetic belt")
    parser.add_argument("--paper-numbering-only", action="store_true", help="skip the label files whose class ids follow another order (a whole-tree box saved as class 5)")
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    start = time.perf_counter()
    excluded = tree_as_five(args.labels) if args.paper_numbering_only else set()
    items = load_crops(Path(args.images), Path(args.labels), args.min_side, args.margin, args.seed, excluded)
    splits = {s: [it for it in items if it["split"] == s] for s in ("train", "val", "test")}
    photos = {s: {it["photo"] for it in v} for s, v in splits.items()}
    assert not (photos["train"] & photos["val"]) and not (photos["train"] & photos["test"]) and not (photos["val"] & photos["test"])
    counts = {s: {c: sum(it["label"] == i for it in v) for i, c in enumerate(CLASSES)} for s, v in splits.items()}
    print(f"crops loaded in {time.perf_counter() - start:.0f} s: {json.dumps(counts)}; photos {({s: len(p) for s, p in photos.items()})}", flush=True)
    masks = attach_masks(splits["train"]) if args.composite else None
    if masks:
        print(f"fruit masks for compositing: {masks}", flush=True)
    train_tf, plain = transforms_for(args.img_size)
    train_loader = DataLoader(Crops(splits["train"], train_tf, args.composite, args.seed), batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(Crops(splits["val"], plain), batch_size=256)
    test_loader = DataLoader(Crops(splits["test"], plain), batch_size=256)
    model = build_model(len(CLASSES), pretrained=True)
    n_train = torch.tensor([counts["train"][c] for c in CLASSES], dtype=torch.float)
    criterion = nn.CrossEntropyLoss(weight=n_train.sum() / (len(CLASSES) * n_train))
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs * len(train_loader))
    best, best_state, history = -1.0, None, []
    for epoch in range(args.epochs):
        model.train()
        t0 = time.perf_counter()
        total = 0.0
        for x, y in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            scheduler.step()
            total += float(loss) * len(y)
        logits, y = logits_of(model, val_loader)
        rec = recalls(logits.argmax(1), y, len(CLASSES))
        balanced = float(np.mean(rec))
        history.append({"epoch": epoch, "train_loss": total / len(splits["train"]), "val_balanced_accuracy": balanced, "val_recall": dict(zip(CLASSES, rec)), "seconds": time.perf_counter() - t0})
        print(f"epoch {epoch:2d} loss {total / len(splits['train']):.4f} val balanced {balanced:.4f} recall {dict(zip(CLASSES, [round(r, 3) for r in rec]))} {time.perf_counter() - t0:.0f} s", flush=True)
        if balanced > best:
            best = balanced
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    val_logits, val_y = logits_of(model, val_loader)
    temperature = fit_temperature(val_logits, val_y)
    val_probs = torch.softmax(val_logits / temperature, 1)
    reject_below = reject_threshold(val_probs, val_y, args.target_accuracy)
    test_logits, test_y = logits_of(model, test_loader)
    test_probs = torch.softmax(test_logits / temperature, 1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model_state": model.state_dict(), "classes": CLASSES, "img_size": args.img_size, "temperature": temperature, "reject_below": reject_below, "mean": MEAN, "std": STD, "version": out.stem, "class_map": {SOURCE_NAMES[k]: v for k, v in SOURCE.items()}, "composite_share": args.composite, "train_belts": list(TRAIN_BELTS) if args.composite else []}, out)
    evaluation = {
        "model": {"file": out.name, "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "architecture": "MobileNetV3-Small (ImageNet pretrained)", "img_size": args.img_size, "classes": CLASSES, "temperature": temperature, "reject_below": reject_below},
        "data": {
            "source": DATA_SOURCE,
            "excluded_label_files": {"n": len(excluded), "rule": "file has a class-5 box covering at least 60% of the photo: that file numbers 'tree' as 5, unlike the paper (0 tree ... 5 spoilt); its other ids cannot be mapped with confidence"} if excluded else None,
            "compositing": {"share": args.composite, "masks": masks, "belts": list(TRAIN_BELTS), "held_out_belts_never_used_in_training": ["azul", "azul-claro"]} if args.composite else None,
            "class_map": {SOURCE_NAMES[k]: v for k, v in SOURCE.items()},
            "min_box_side_px": args.min_side,
            "split": "by source photo (sha256 of file name), 70/15/15; no photo appears in two splits",
            "counts": counts,
            "photos": {s: len(p) for s, p in photos.items()},
            "selection": "checkpoint with best validation balanced accuracy; temperature and reject threshold fitted on validation; test used once",
        },
        "training": {"epochs": args.epochs, "batch_size": args.batch_size, "lr": args.lr, "seed": args.seed, "history": history, "seconds": time.perf_counter() - start},
        "validation": report(val_probs, val_y, splits["val"], reject_below, args.bootstrap, args.seed),
        "test": report(test_probs, test_y, splits["test"], reject_below, args.bootstrap, args.seed),
        "test_uncalibrated_ece": ece(torch.softmax(test_logits, 1), test_y),
        "test_predictions": {"y": test_y.tolist(), "p": [[round(float(v), 5) for v in row] for row in test_probs], "photo": [it["photo"] for it in splits["test"]]},
    }
    out.with_name(out.stem + "_eval.json").write_text(json.dumps(evaluation, indent=1) + "\n", encoding="utf-8")
    t = evaluation["test"]
    print(f"test n={t['n']} photos={t['photos']} acc={t['accuracy']:.3f} {t['accuracy_ci95_cluster_bootstrap']} balanced={t['balanced_accuracy']:.3f} baseline={t['majority_baseline_accuracy']:.3f} ece={t['ece']:.3f} T={temperature:.2f} reject<{reject_below} coverage={t['with_reject']['coverage']:.3f} acc_accepted={t['with_reject']['accuracy_on_accepted']}", flush=True)
    print(json.dumps(t["per_class"], indent=1))


if __name__ == "__main__":
    main()
