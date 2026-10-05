import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from train import build_model

GOOD = ("boa", "nao_podre")


class CropClassifier:
    def __init__(self, checkpoint, device="cpu"):
        ck = torch.load(checkpoint, map_location=device)
        self.classes = list(ck["classes"])
        self.size = int(ck.get("img_size", 224))
        self.temperature = float(ck.get("temperature", 1.0))
        self.reject_below = ck.get("reject_below")
        self.version = ck.get("version", Path(checkpoint).stem)
        self.mean = np.array(ck.get("mean", [0.485, 0.456, 0.406]), np.float32)
        self.std = np.array(ck.get("std", [0.229, 0.224, 0.225]), np.float32)
        self.device = device
        self.model = build_model(len(self.classes), pretrained=False)
        self.model.load_state_dict(ck["model_state"])
        self.model.to(device).eval()

    def needs_review(self, confidence):
        return self.reject_below is None or confidence < self.reject_below

    def probs(self, crops_bgr):
        batch = []
        for crop in crops_bgr:
            image = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)).resize((self.size, self.size), Image.BILINEAR)
            rgb = np.asarray(image, dtype=np.float32) / 255
            batch.append(((rgb - self.mean) / self.std).transpose(2, 0, 1))
        with torch.no_grad():
            logits = self.model(torch.from_numpy(np.stack(batch)).to(self.device))
            return torch.softmax(logits / self.temperature, dim=1).cpu().numpy()


class ModelDecider:
    def __init__(self, classifier, min_size_mm=None):
        self.classifier = classifier
        self.min_size_mm = min_size_mm

    def __call__(self, track):
        size = float(np.median(track["sizes"])) if track["sizes"] else None
        if not track["views"]:
            return {"label": "indefinido", "confidence": None, "probs": {}, "views": 0, "size_mm": size, "needs_review": True, "decided_by": "sem_vista"}
        p = self.classifier.probs(track["views"]).mean(axis=0)
        k = int(p.argmax())
        label, confidence = self.classifier.classes[k], float(p[k])
        decided_by = "modelo"
        if self.min_size_mm and size is not None and size < self.min_size_mm and label in GOOD:
            label, decided_by = "baixa_qualidade", "regra_calibre"
        review = self.classifier.needs_review(confidence)
        return {"label": label, "confidence": confidence, "probs": {c: round(float(v), 4) for c, v in zip(self.classifier.classes, p)}, "views": len(track["views"]), "size_mm": size, "needs_review": bool(review), "decided_by": decided_by}


class TruthDecider:
    def __init__(self, simulator):
        self.simulator = simulator

    def __call__(self, track):
        fruit = self.simulator.truth_at(track["cx"], track["cy"])
        size = float(np.median(track["sizes"])) if track["sizes"] else None
        label = fruit["label"] if fruit else "indefinido"
        return {"label": label, "confidence": None, "probs": {}, "views": len(track["views"]), "size_mm": size, "needs_review": fruit is None, "decided_by": "simulacao", "truth_id": fruit["id"] if fruit else None}
