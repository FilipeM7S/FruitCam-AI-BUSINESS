import csv
import hashlib
import re
import time
from pathlib import Path

import cv2
import numpy as np

LABELS = ("boa", "baixa_qualidade", "podre", "sem_rotulo")
FIELDS = ["file", "batch", "label", "camera", "run", "track_id", "view", "fruit", "size_mm", "t", "recorded_at", "source", "px_per_mm"]
BATCH = re.compile(r"^[A-Za-z0-9._-]{1,60}$")


def read_manifest(root):
    path = Path(root) / "manifest.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TrayRecorder:
    def __init__(self, root, batch, label, camera, source, px_per_mm, frames_every=2.0):
        if label not in LABELS:
            raise ValueError(f"label must be one of {LABELS}")
        if not BATCH.match(batch):
            raise ValueError("batch: letters, digits, '.', '_' or '-' only")
        self.root = Path(root)
        clash = {r["label"] for r in read_manifest(self.root) if r["batch"] == batch} - {label}
        if clash:
            raise ValueError(f"batch {batch!r} was already recorded as {sorted(clash)}; one tray = one label")
        self.batch, self.label, self.camera, self.source, self.px_per_mm = batch, label, camera, source, px_per_mm
        self.run = time.strftime("%Y%m%dT%H%M%S")
        self.dir = self.root / batch / label
        self.frames_dir = self.root / batch / "frames"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = self.root / "manifest.csv"
        self.frames_every = frames_every
        self.last_frame = None
        self.fruits = 0
        self.crops = 0
        self.frames = 0

    def __call__(self, track):
        size = float(np.median(track["sizes"])) if track["sizes"] else None
        fruit = f"{self.batch}/{self.run}/{track['id']}"
        rows = []
        for i, view in enumerate(track["views"]):
            name = f"{self.camera}-{self.batch}-{self.run}-{track['id']:05d}-{i}.jpg"
            cv2.imwrite(str(self.dir / name), view, [cv2.IMWRITE_JPEG_QUALITY, 95])
            rows.append({"file": f"{self.batch}/{self.label}/{name}", "batch": self.batch, "label": self.label, "camera": self.camera, "run": self.run, "track_id": track["id"], "view": i, "fruit": fruit, "size_mm": "" if size is None else round(size, 1), "t": round(track["t"], 3), "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": self.source, "px_per_mm": self.px_per_mm})
        if rows:
            new = not self.manifest.exists()
            with self.manifest.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                if new:
                    writer.writeheader()
                writer.writerows(rows)
        self.fruits += 1
        self.crops += len(rows)
        unlabelled = self.label == "sem_rotulo"
        return {"label": "indefinido" if unlabelled else self.label, "confidence": None, "probs": {}, "views": len(rows), "size_mm": size, "needs_review": unlabelled, "decided_by": "bandeja"}

    def frame(self, t, frame):
        if self.last_frame is not None and t - self.last_frame < self.frames_every:
            return
        self.last_frame = t
        cv2.imwrite(str(self.frames_dir / f"{self.camera}-{self.batch}-{self.run}-{t:010.2f}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        self.frames += 1


def order(batch, seed):
    return hashlib.sha256(f"{seed}:{batch}".encode()).hexdigest()


def split_by_batch(rows, seed=0, val_share=0.15):
    labelled = [r for r in rows if r["label"] != "sem_rotulo"]
    batches = {}
    for r in labelled:
        batches.setdefault(r["label"], set()).add(r["batch"])
    assign, notes = {}, []
    for label, names in sorted(batches.items()):
        ranked = sorted(names, key=lambda b: order(b, seed))
        if len(ranked) < 2:
            raise ValueError(f"label {label!r} has only {len(ranked)} batch; record at least two separate trays per class so test fruit never appear in training")
        assign[ranked[0]] = "test"
        if len(ranked) >= 3:
            assign[ranked[1]] = "val"
            rest = ranked[2:]
        else:
            rest = ranked[1:]
            notes.append(f"{label}: 2 batches, validation taken from training fruit of the same batch")
        for b in rest:
            assign[b] = "train"
    out = {"train": [], "val": [], "test": []}
    for r in labelled:
        split = assign[r["batch"]]
        if split == "train" and not any(assign.get(b) == "val" for b in batches[r["label"]]):
            if int(order(r["fruit"], seed)[:8], 16) / 0xFFFFFFFF < val_share:
                split = "val"
        out[split].append(r)
    return out, {"batches": dict(sorted(assign.items())), "notes": notes}
