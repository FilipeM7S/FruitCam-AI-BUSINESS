import math

import cv2
import numpy as np


class BeltDetector:
    def __init__(self, px_per_mm, min_area_mm2=250.0, max_area_mm2=8000.0, threshold=14.0, lightness_weight=0.5, rows=None, adapt=0.02, neck=0.7, bridge=0.0, peak=0.9, seal=False):
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
        self.neck = neck
        self.bridge = bridge
        self.peak = peak
        self.seal = seal
        self.bridges = 0
        radius = max(int(round(math.sqrt(self.min_area / math.pi))), 4)
        self.core = 0.3 * radius
        self.reach = np.ones((2 * (radius // 2) + 1, 2 * (radius // 2) + 1), np.uint8)
        self.splits = 0

    def _region(self, a):
        return a[self.rows[0]:self.rows[1]] if self.rows else a

    def _bridge(self, mask, dist):
        weak = ((dist > self.bridge * self.threshold) & (mask == 0)).astype(np.uint8)
        if self.rows:
            weak[: self.rows[0]] = 0
            weak[self.rows[1]:] = 0
        weak &= cv2.dilate(mask, self.reach)
        if not weak.any():
            return mask
        n_parts, part_of = cv2.connectedComponents(mask, connectivity=8)
        if n_parts <= 2:
            return mask
        _, group_of, stats, _ = cv2.connectedComponentsWithStats(mask | weak, connectivity=8)
        solid = mask > 0
        groups, parts_in = np.unique(np.unique(group_of[solid].astype(np.int64) * n_parts + part_of[solid]) // n_parts, return_counts=True)
        joined = None
        for group in groups[parts_in >= 2]:
            x, y, w, h, _ = (int(v) for v in stats[group])
            window = (slice(y, y + h), slice(x, x + w))
            mine = group_of[window] == group
            hull = np.zeros((h, w), np.uint8)
            cv2.fillConvexPoly(hull, cv2.convexHull(cv2.findNonZero((mine & solid[window]).astype(np.uint8))), 1)
            joined = mask.copy() if joined is None else joined
            joined[window] |= (hull > 0) & mine & (weak[window] > 0)
        if joined is None:
            return mask
        self.bridges += 1
        return joined

    def _separate(self, mask):
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        seeds = ((dist >= self.peak * cv2.dilate(dist, self.reach)) & (dist >= self.core)).astype(np.uint8)
        n_seeds, seed_of = cv2.connectedComponents(seeds, connectivity=8)
        if n_seeds <= 2:
            return mask
        _, blob_of, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        at = seeds > 0
        owners = np.unique(blob_of[at].astype(np.int64) * n_seeds + seed_of[at]) // n_seeds
        blobs, seeds_in = np.unique(owners, return_counts=True)
        cut = None
        for blob in blobs[(seeds_in >= 2) & (blobs > 0)]:
            x, y, w, h, area = (int(v) for v in stats[blob])
            if area < 2 * self.min_area:
                continue
            window = (slice(y, y + h), slice(x, x + w))
            body = (blob_of[window] == blob).astype(np.uint8)
            lines = self._necks(body, dist[window], (seeds[window] & body))
            if lines is not None:
                cut = mask.copy() if cut is None else cut
                cut[window][lines] = 0
        if cut is None:
            return mask
        self.splits += 1
        return cut

    def _necks(self, body, dist, seeds):
        _, nearest = cv2.distanceTransformWithLabels(1 - seeds, cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_CCOMP)
        cells = nearest * body.astype(np.int32)
        top = int(cells.max()) + 1
        pairs, heights = [], []
        for a, b, da, db in ((cells[:, :-1], cells[:, 1:], dist[:, :-1], dist[:, 1:]), (cells[:-1], cells[1:], dist[:-1], dist[1:])):
            edge = (a != b) & (a > 0) & (b > 0)
            if edge.any():
                pairs.append(np.minimum(a[edge], b[edge]).astype(np.int64) * top + np.maximum(a[edge], b[edge]))
                heights.append(np.maximum(da[edge], db[edge]))
        if not pairs:
            return None
        keys, where = np.unique(np.concatenate(pairs), return_inverse=True)
        saddle = np.zeros(len(keys), np.float32)
        np.maximum.at(saddle, where, np.concatenate(heights))
        inside = cells > 0
        peak = np.zeros(top, np.float32)
        np.maximum.at(peak, cells[inside], dist[inside])
        area = np.bincount(cells[inside], minlength=top)
        parent = list(range(top))

        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for k in np.argsort(-saddle):
            a, b = root(int(keys[k] // top)), root(int(keys[k] % top))
            if a != b and (saddle[k] >= self.neck * min(peak[a], peak[b]) or min(area[a], area[b]) < self.min_area):
                parent[b] = a
                peak[a] = max(peak[a], peak[b])
                area[a] += area[b]
        merged = np.array([root(i) for i in range(top)])[cells]
        lines = np.zeros(body.shape, bool)
        across = (merged[:, :-1] != merged[:, 1:]) & (merged[:, :-1] > 0) & (merged[:, 1:] > 0)
        down = (merged[:-1] != merged[1:]) & (merged[:-1] > 0) & (merged[1:] > 0)
        lines[:, 1:] |= across
        lines[1:] |= down
        if self.seal:
            lines[:, :-1] |= across
            lines[:-1] |= down
        return lines if lines.any() else None

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
        if self.bridge:
            mask = self._bridge(mask, dist)
        whole = mask
        if self.neck:
            mask = self._separate(mask)
        cuts = (whole > 0) & (mask == 0) if mask is not whole else None
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
                "cut": bool(cuts is not None and cuts[max(y - 2, 0):y + bh + 2, max(x - 2, 0):x + bw + 2].any()),
            })
        return found, mask
