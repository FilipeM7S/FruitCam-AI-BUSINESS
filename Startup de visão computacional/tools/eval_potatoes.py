import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageDraw
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from belt.detect import BeltDetector
from train import build_model
from train_belt import cluster_bootstrap, ece, fit_temperature, logits_of, transforms_for, wilson

DATA = ROOT / "data" / "external" / "potatoes" / "extracted" / "dataset_potatoes" / "dataset_potatoes"
OUT = ROOT / "docs" / "datasets" / "potatoes"
CLASSES = ["Good", "Damaged", "Plant", "Stone"]
SOURCE = {"doi": "10.5281/zenodo.17494608", "url": "https://zenodo.org/records/17494608", "title": "Potatoes Dataset", "authors": "Štursa, Dominik; Doležel, Petr; Ksiažek, Jakub (University of Pardubice)", "license": "CC BY 4.0", "zip_md5": "6e75a6ed39e929ee646dd002767531e7"}


def variants(a):
    for k in range(4):
        r = np.rot90(a, k)
        yield np.ascontiguousarray(r)
        yield np.ascontiguousarray(r[:, ::-1])


def digest(a):
    return hashlib.sha1(a.tobytes()).hexdigest()


def signature(a):
    g = np.asarray(Image.fromarray(a).convert("L").resize((8, 8), Image.BILINEAR), dtype=np.float64).ravel()
    return (g - g.mean()) / (g.std() + 1e-6)


def load(near):
    files = sorted(DATA.glob("*/*/*.bmp"))
    objects = {}
    for p in files:
        a = np.asarray(Image.open(p).convert("RGB"))
        key = min(digest(v) for v in variants(a))
        entry = objects.setdefault(key, {"key": key, "image": a, "label": p.parts[-2], "official": set(), "copies": 0})
        assert entry["label"] == p.parts[-2]
        entry["official"].add(p.parts[-3])
        entry["copies"] += 1
    items = list(objects.values())
    sigs = np.stack([np.stack([signature(v) for v in variants(it["image"])]) for it in items])
    base = sigs[:, 0]
    corr = np.max(np.einsum("id,jvd->ijv", base, sigs) / base.shape[1], axis=2)
    np.fill_diagonal(corr, 0)
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pairs = np.argwhere(np.triu(corr > near))
    for i, j in pairs:
        parent[find(i)] = find(j)
    for i, it in enumerate(items):
        it["group"] = items[find(i)]["key"]
    return files, items, len(pairs)


def segmentation(items, threshold, weight):
    labs = [cv2.cvtColor(np.ascontiguousarray(it["image"][:, :, ::-1]), cv2.COLOR_BGR2LAB).astype(np.float32) for it in items]
    corners = np.concatenate([np.concatenate([l[:5, :5], l[:5, -5:], l[-5:, :5], l[-5:, -5:]]).reshape(-1, 3) for l in labs])
    belt = np.median(corners, axis=0)
    detector = BeltDetector(px_per_mm=1.0, min_area_mm2=0, max_area_mm2=10 ** 9, threshold=threshold, lightness_weight=weight, adapt=0)
    rows, masks = [], []
    for it, lab in zip(items, labs):
        detector.belt = belt.copy()
        _, mask = detector.detect(np.ascontiguousarray(it["image"][:, :, ::-1]))
        h, w = mask.shape
        c = mask[h // 2 - 8:h // 2 + 8, w // 2 - 8:w // 2 + 8]
        d = lab[h // 2 - 8:h // 2 + 8, w // 2 - 8:w // 2 + 8] - belt
        dist = float(np.median(np.sqrt((weight * d[..., 0]) ** 2 + d[..., 1] ** 2 + d[..., 2] ** 2)))
        rows.append({"label": it["label"], "centre_foreground": float(c.mean()), "centre_distance": dist, "mask_share": float(mask.mean())})
        masks.append(mask)
    per = {}
    for name in CLASSES:
        r = [x for x in rows if x["label"] == name]
        sep = sum(x["centre_foreground"] >= 0.9 for x in r)
        per[name] = {
            "n": len(r),
            "centre_separated": sep,
            "centre_separated_share": sep / len(r),
            "centre_separated_ci95": wilson(sep, len(r)),
            "median_centre_distance_to_belt": float(np.median([x["centre_distance"] for x in r])),
            "median_mask_share": float(np.median([x["mask_share"] for x in r])),
        }
    return {"belt_lab_opencv": [round(float(v), 1) for v in belt], "threshold": threshold, "lightness_weight": weight, "rule": "object centre (16x16 px) at least 90% foreground with the detector's own Lab rule, belt colour = median of crop corners", "per_class": per}, masks


def sweep(items):
    rows = []
    for weight in (0.5, 1.0):
        for threshold in (6.0, 8.0, 10.0, 12.0, 14.0, 18.0):
            seg, masks = segmentation(items, threshold, weight)
            pc = seg["per_class"]
            corners = np.mean([np.concatenate([m[:4, :4].ravel(), m[:4, -4:].ravel(), m[-4:, :4].ravel(), m[-4:, -4:].ravel()]).mean() for m in masks])
            rows.append({
                "lightness_weight": weight,
                "threshold": threshold,
                "potato_centres_separated": (pc["Good"]["centre_separated"] + pc["Damaged"]["centre_separated"]) / (pc["Good"]["n"] + pc["Damaged"]["n"]),
                "stone_centres_separated": pc["Stone"]["centre_separated_share"],
                "plant_centres_separated": pc["Plant"]["centre_separated_share"],
                "corner_pixels_marked_foreground": float(corners),
            })
    return rows


def cashew_contrast(belt, weight, thresholds):
    from train_belt import load_crops, tree_as_five
    items = load_crops(ROOT / "images", ROOT / "Labels", 16, 0.0, 0, tree_as_five(ROOT / "Labels"))
    dist = {}
    for it in items:
        a = np.asarray(it["image"].resize((32, 32), Image.BILINEAR))[8:24, 8:24]
        lab = cv2.cvtColor(np.ascontiguousarray(a[:, :, ::-1]), cv2.COLOR_BGR2LAB).astype(np.float32) - belt
        dist.setdefault(it["source"], []).append(float(np.median(np.sqrt((weight * lab[..., 0]) ** 2 + lab[..., 1] ** 2 + lab[..., 2] ** 2))))
    return {
        "what": "median Lab distance between the centre of each real cashew crop (field photos, box without margin, label files with the paper's class numbering only, boxes >= 16 px) and the colour of this real potato belt, with the detector's formula",
        "lightness_weight": weight,
        "per_source_label": {k: {"n": len(v), "median_distance": float(np.median(v)), "share_above": {str(t): float(np.mean(np.array(v) > t)) for t in thresholds}} for k, v in sorted(dist.items())},
    }


def sheet(items, masks, path, per_class=10):
    rng = random.Random(0)
    tile = 100
    img = Image.new("RGB", (per_class * 2 * (tile + 4) + 8, len(CLASSES) * (tile + 4) + 8), (20, 35, 30))
    for r, name in enumerate(CLASSES):
        idx = [i for i, it in enumerate(items) if it["label"] == name]
        for k, i in enumerate(rng.sample(idx, per_class)):
            x = 4 + k * 2 * (tile + 4)
            y = 4 + r * (tile + 4)
            img.paste(Image.fromarray(items[i]["image"]).resize((tile, tile), Image.NEAREST), (x, y))
            m = Image.fromarray((masks[i] * 255).astype(np.uint8)).resize((tile, tile), Image.NEAREST).convert("RGB")
            img.paste(m, (x + tile + 4, y))
        ImageDraw.Draw(img).text((6, 6 + r * (tile + 4)), name, fill=(255, 210, 0))
    img.save(path)


class Objects(Dataset):
    def __init__(self, items, tf):
        self.items = items
        self.tf = tf

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        return self.tf(Image.fromarray(self.items[i]["image"])), CLASSES.index(self.items[i]["label"])


def fold_of(group, folds, seed):
    return int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16) % folds


def train_fold(train_items, val_items, size, epochs, seed):
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    train_tf, plain = transforms_for(size)
    loader = DataLoader(Objects(train_items, train_tf), batch_size=32, shuffle=True)
    val_loader = DataLoader(Objects(val_items, plain), batch_size=128)
    model = build_model(len(CLASSES), pretrained=True)
    counts = torch.tensor([sum(it["label"] == c for it in train_items) for c in CLASSES], dtype=torch.float)
    criterion = nn.CrossEntropyLoss(weight=counts.sum() / (len(CLASSES) * counts.clamp(min=1)))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs * len(loader))
    best, state = -1.0, None
    for _ in range(epochs):
        model.train()
        for x, y in loader:
            optimizer.zero_grad()
            criterion(model(x), y).backward()
            optimizer.step()
            scheduler.step()
        logits, y = logits_of(model, val_loader)
        pred = logits.argmax(1)
        bal = float(np.mean([float((pred[y == c] == c).float().mean()) for c in range(len(CLASSES)) if (y == c).any()]))
        if bal > best:
            best, state = bal, {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(state)
    logits, y = logits_of(model, val_loader)
    return model, fit_temperature(logits, y), plain


def classification(items, folds, size, epochs, seed, draws):
    probs = np.zeros((len(items), len(CLASSES)))
    temps = []
    for f in range(folds):
        test = [i for i, it in enumerate(items) if fold_of(it["group"], folds, seed) == f]
        rest = [i for i, it in enumerate(items) if fold_of(it["group"], folds, seed) != f]
        val = [i for i in rest if fold_of(items[i]["group"], 7, seed + 1) == 0]
        train = [i for i in rest if i not in set(val)]
        t0 = time.perf_counter()
        model, temperature, plain = train_fold([items[i] for i in train], [items[i] for i in val], size, epochs, seed + f)
        logits, _ = logits_of(model, DataLoader(Objects([items[i] for i in test], plain), batch_size=128))
        probs[test] = torch.softmax(logits / temperature, 1).numpy()
        temps.append(temperature)
        print(f"fold {f}: train {len(train)} val {len(val)} test {len(test)} T={temperature:.2f} {time.perf_counter() - t0:.0f} s", flush=True)
    y = np.array([CLASSES.index(it["label"]) for it in items])
    pred = probs.argmax(1)
    correct = (pred == y).astype(float)
    k = len(CLASSES)
    confusion = [[int(((y == i) & (pred == j)).sum()) for j in range(k)] for i in range(k)]
    acc_ci, bal_ci = cluster_bootstrap([it["group"] for it in items], correct, y, k, draws, seed)
    per = {}
    for c, name in enumerate(CLASSES):
        tp, support, predicted = confusion[c][c], sum(confusion[c]), sum(confusion[i][c] for i in range(k))
        per[name] = {"support": support, "recall": tp / support, "recall_ci95": wilson(tp, support), "precision": tp / predicted if predicted else None, "precision_ci95": wilson(tp, predicted)}
    potato = np.isin(y, [0, 1])
    good_pred = pred == 0
    binary_correct = (good_pred[potato] == (y[potato] == 0)).astype(float)
    damaged = y == 1
    return {
        "protocol": f"{folds}-fold cross-validation, folds by object group (rotated/flipped copies and near-duplicates kept together); in each fold 1/7 of the training groups is validation for checkpoint choice and temperature",
        "img_size": size,
        "epochs": epochs,
        "n": int(len(y)),
        "groups": len({it["group"] for it in items}),
        "accuracy": float(correct.mean()),
        "accuracy_ci95_group_bootstrap": acc_ci,
        "balanced_accuracy": float(np.mean([per[c]["recall"] for c in CLASSES])),
        "balanced_accuracy_ci95_group_bootstrap": bal_ci,
        "majority_baseline_accuracy": max(sum(r) for r in confusion) / len(y),
        "confusion": confusion,
        "per_class": per,
        "good_vs_not_good_on_potatoes": {"n": int(potato.sum()), "accuracy": float(binary_correct.mean()), "accuracy_ci95": wilson(int(binary_correct.sum()), int(potato.sum()))},
        "damaged_predicted_good": {"k": int((good_pred & damaged).sum()), "n": int(damaged.sum()), "rate_ci95": wilson(int((good_pred & damaged).sum()), int(damaged.sum()))},
        "ece": ece(torch.tensor(probs, dtype=torch.float), torch.tensor(y)),
        "temperatures": temps,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--near", type=float, default=0.95)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--img-size", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--skip-training", action="store_true")
    args = parser.parse_args()
    start = time.perf_counter()
    files, items, near_pairs = load(args.near)
    official = {}
    for it in items:
        official.setdefault(" + ".join(sorted(it["official"])), 0)
        official[" + ".join(sorted(it["official"]))] += 1
    leaked = sum(1 for it in items if len(it["official"] & {"test1", "test2", "test3"}) and len(it["official"] & {"train", "val"}))
    exact = len({digest(np.asarray(Image.open(p).convert("RGB"))) for p in files})
    data = {
        "source": SOURCE,
        "files": len(files),
        "image_size": list(items[0]["image"].shape[1::-1]),
        "exact_unique_images": exact,
        "unique_up_to_rotation_and_flip": len(items),
        "near_duplicate_pairs_merged": int(near_pairs),
        "near_duplicate_rule": f"8x8 grey signature correlation > {args.near} under any rotation/flip",
        "object_groups": len({it["group"] for it in items}),
        "objects_per_class": {c: sum(it["label"] == c for it in items) for c in CLASSES},
        "objects_by_official_split_membership": dict(sorted(official.items(), key=lambda kv: -kv[1])),
        "test_objects_also_in_train_or_val": leaked,
        "test_objects_total": sum(1 for it in items if it["official"] & {"test1", "test2", "test3"}),
        "contains_full_frames_or_sequences": False,
    }
    print(json.dumps(data, ensure_ascii=False, indent=1), flush=True)
    seg, masks = segmentation(items, 14.0, 0.5)
    sheet(items, masks, OUT / "segmentation_sheet.png")
    print(json.dumps(seg, indent=1), flush=True)
    seg["sweep"] = sweep(items)
    seg["cashew_colour_vs_this_belt"] = cashew_contrast(np.array(seg["belt_lab_opencv"], dtype=np.float32), 0.5, (14.0, 20.0))
    print(json.dumps(seg["cashew_colour_vs_this_belt"], indent=1), flush=True)
    result = {"what": "Real industrial potato sorting belt (Zenodo 17494608), used to check the FruitCam segmentation rule and training recipe on real belt imagery. Not cashew; tracking and counting cannot be tested because the dataset has only single-object 50x50 crops.", "data": data, "segmentation": seg}
    if not args.skip_training:
        result["classification"] = classification(items, args.folds, args.img_size, args.epochs, args.seed, args.bootstrap)
        print(json.dumps({k: v for k, v in result["classification"].items() if k != "per_class"}, indent=1), flush=True)
    result["seconds"] = round(time.perf_counter() - start)
    (OUT / "potato_eval.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
