import copy
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image

from belt.classify import CropClassifier

FLAG = "FRUITCAM_TTST"
CLASSES = ["boa", "baixa_qualidade", "podre"]
ROTTEN = CLASSES.index("podre")


def enabled():
    return os.environ.get(FLAG) == "1"


class Buffer:
    def __init__(self, threshold=0.9, per_class=400):
        self.threshold = threshold
        self.per_class = per_class
        self.items = {}
        self.offered = 0
        self.refused = 0

    def offer(self, key, crop, probs):
        self.offered += 1
        label = int(np.argmax(probs))
        confidence = float(probs[label])
        held = self.items.get(key)
        if confidence < self.threshold or (held and held["origin"] == "operator"):
            self.refused += 1
            return False
        self.items[key] = {"crop": crop, "label": label, "origin": "pseudo", "confidence": confidence}
        mine = [k for k, v in self.items.items() if v["origin"] == "pseudo" and v["label"] == label]
        for old in mine[: max(0, len(mine) - self.per_class)]:
            del self.items[old]
        return True

    def correct(self, key, crop, label):
        self.items[key] = {"crop": crop, "label": int(label), "origin": "operator", "confidence": None}

    def counts(self):
        return {name: {origin: sum(v["label"] == i and v["origin"] == origin for v in self.items.values()) for origin in ("pseudo", "operator")} for i, name in enumerate(CLASSES)}

    def smallest_class(self):
        return min(sum(v.values()) for v in self.counts().values())


def tensors(classifier, crops):
    batch = []
    for crop in crops:
        image = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)).resize((classifier.size, classifier.size), Image.BILINEAR)
        rgb = np.asarray(image, dtype=np.float32) / 255
        batch.append(((rgb - classifier.mean) / classifier.std).transpose(2, 0, 1))
    return torch.from_numpy(np.stack(batch))


def measure(classifier, crops, labels, batch=128):
    classifier.model.eval()
    pred = np.concatenate([classifier.probs(crops[i:i + batch]).argmax(axis=1) for i in range(0, len(crops), batch)])
    y = np.asarray(labels)
    recalls = [float((pred[y == c] == c).mean()) for c in range(len(CLASSES)) if (y == c).any()]
    rotten = y == ROTTEN
    return {"n": int(len(y)), "balanced_accuracy": float(np.mean(recalls)), "rotten_recall": float((pred[rotten] == ROTTEN).mean()) if rotten.any() else None, "n_rotten": int(rotten.sum()), "accuracy": float((pred == y).mean())}


class Adapter:
    def __init__(self, checkpoint, control, log, lr=1e-4, steps=60, batch=32, max_update=0.05, min_per_class=30, tolerance=0.005, operator_weight=3.0, seed=0):
        self.checkpoint = Path(checkpoint)
        self.classifier = CropClassifier(self.checkpoint)
        self.control = control
        self.log = Path(log)
        self.lr, self.steps, self.batch = lr, steps, batch
        self.max_update, self.min_per_class, self.tolerance = max_update, min_per_class, tolerance
        self.operator_weight = operator_weight
        self.rng = np.random.default_rng(seed)
        self.updates = 0
        self.refused_state = None

    def record(self, entry):
        entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "update": self.updates, "base_model": self.checkpoint.name, **entry}
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def step(self, buffer):
        if not enabled():
            raise RuntimeError(f"test-time self-training is off; it only runs with {FLAG}=1")
        shared = set(buffer.items) & set(self.control["keys"])
        if shared:
            raise ValueError(f"{len(shared)} control items are also in the training buffer; the control set is never trained on")
        self.updates += 1
        counts = buffer.counts()
        if buffer.smallest_class() < self.min_per_class:
            return self.record({"status": "skipped", "reason": f"a class has fewer than {self.min_per_class} items in the buffer", "buffer": counts})
        model = self.classifier.model
        before = measure(self.classifier, self.control["crops"], self.control["labels"])
        start = copy.deepcopy(model.state_dict())
        items = list(buffer.items.values())
        by_class = [[i for i, v in enumerate(items) if v["label"] == c] for c in range(len(CLASSES))]
        weight = torch.tensor([self.operator_weight if v["origin"] == "operator" else 1.0 for v in items])
        optimiser = torch.optim.Adam(model.parameters(), lr=self.lr)
        loss_fn = nn.CrossEntropyLoss(reduction="none")
        model.train()
        losses = []
        for _ in range(self.steps):
            picked = np.concatenate([self.rng.choice(rows, self.batch // len(CLASSES)) for rows in by_class])
            x = tensors(self.classifier, [items[i]["crop"] for i in picked])
            y = torch.tensor([items[i]["label"] for i in picked])
            loss = (loss_fn(model(x), y) * weight[picked]).sum() / weight[picked].sum()
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            losses.append(float(loss.detach()))
        model.eval()
        end = model.state_dict()
        moving = [k for k, v in end.items() if v.dtype.is_floating_point]
        change = float(torch.sqrt(sum(((end[k] - start[k]) ** 2).sum() for k in moving)) / torch.sqrt(sum((start[k] ** 2).sum() for k in moving)))
        scale = min(1.0, self.max_update / change) if change > 0 else 1.0
        if scale < 1.0:
            model.load_state_dict({k: start[k] + scale * (end[k] - start[k]) if k in moving else start[k] for k in end})
        after = measure(self.classifier, self.control["crops"], self.control["labels"])
        worse = [name for name in ("balanced_accuracy", "rotten_recall") if after[name] is not None and after[name] < before[name] - self.tolerance]
        self.refused_state = None
        if worse:
            self.refused_state = copy.deepcopy(model.state_dict())
            model.load_state_dict(start)
        return self.record({
            "status": "rolled_back" if worse else "accepted",
            "reason": f"{' and '.join(worse)} fell by more than {self.tolerance} on the control set" if worse else "no drop on the control set beyond the tolerance",
            "buffer": counts,
            "buffer_threshold": buffer.threshold,
            "steps": self.steps,
            "lr": self.lr,
            "loss_first_last": [losses[0], losses[-1]],
            "relative_change_before_limit": change,
            "max_update": self.max_update,
            "relative_change_applied": 0.0 if worse else change * scale,
            "control_before": before,
            "control_after": after,
        })

    def save(self, path):
        path = Path(path)
        ck = torch.load(self.checkpoint, map_location="cpu")
        torch.save({**ck, "model_state": self.classifier.model.state_dict(), "version": path.stem, "adapted_from": self.checkpoint.name, "reject_below": None, "adaptation": {"method": "test-time self-training", "updates": self.updates, "log": self.log.name}}, path)
        return path
