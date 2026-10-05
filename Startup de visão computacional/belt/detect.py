import math

import cv2
import numpy as np


class BeltDetector:
    def __init__(self, px_per_mm, min_area_mm2=250.0, max_area_mm2=8000.0, threshold=14.0, lightness_weight=0.5, rows=None, adapt=0.02):
        self.px_per_mm = px_per_mm
        self.min_area = min_area_mm2 * px_per_mm ** 2
        self.max_area = max_area_mm2 * px_per_mm ** 2
        self.threshold = threshold
        self.weight = lightness_weight
        self.rows = rows
        self.adapt = adapt
        self.belt = None
        self.frames = 0
        self.open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))

    def _region(self, a):
        return a[self.rows[0]:self.rows[1]] if self.rows else a

    def detect(self, frame):
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
        if self.belt is None:
            self.belt = np.median(self._region(lab).reshape(-1, 3), axis=0)
        d = lab - self.belt
        dist = np.sqrt((self.weight * d[..., 0]) ** 2 + d[..., 1] ** 2 + d[..., 2] ** 2)
        mask = (dist > self.threshold).astype(np.uint8)
        if self.rows:
            mask[: self.rows[0]] = 0
            mask[self.rows[1]:] = 0
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.open)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.close)
        self.frames += 1
        background = self._region(mask) == 0
        if self.adapt and self.frames % 10 == 0 and background.any():
            self.belt = (1 - self.adapt) * self.belt + self.adapt * np.median(self._region(lab)[background][::7], axis=0)
        n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        h, w = mask.shape
        found = []
        for i in range(1, n):
            x, y, bw, bh, area = (int(v) for v in stats[i])
            if not self.min_area <= area <= self.max_area:
                continue
            found.append({
                "box": (x, y, x + bw - 1, y + bh - 1),
                "centroid": (float(centroids[i][0]), float(centroids[i][1])),
                "area_mm2": area / self.px_per_mm ** 2,
                "diameter_mm": 2 * math.sqrt(area / math.pi) / self.px_per_mm,
                "edge": x == 0 or y == 0 or x + bw >= w or y + bh >= h,
            })
        return found, mask
