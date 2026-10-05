import math

import numpy as np


def square_crop(frame, box, margin=0.15):
    x0, y0, x1, y1 = box
    side = max(x1 - x0, y1 - y0) * (1 + margin)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    h, w = frame.shape[:2]
    a, b = int(max(cx - side / 2, 0)), int(max(cy - side / 2, 0))
    c, d = int(min(cx + side / 2, w)), int(min(cy + side / 2, h))
    return frame[b:d, a:c].copy()


class Tracker:
    def __init__(self, line_x, direction=1, max_missed=6, gate_px=60.0, views_every=2, max_views=6):
        self.line = line_x
        self.direction = direction
        self.max_missed = max_missed
        self.gate = gate_px
        self.views_every = views_every
        self.max_views = max_views
        self.tracks = []
        self.next_id = 1
        self.velocity = 0.0
        self.crossed = 0

    def _predict(self, track, t):
        vx = track["vx"] if track["hits"] >= 2 else self.velocity
        return track["cx"] + vx * (t - track["t"]), track["cy"]

    def update(self, t, detections, frame):
        pairs = []
        for i, tr in enumerate(self.tracks):
            px, py = self._predict(tr, t)
            for j, det in enumerate(detections):
                dist = math.hypot(det["centroid"][0] - px, det["centroid"][1] - py)
                if dist <= max(self.gate, 0.6 * math.sqrt(det["area_mm2"])):
                    pairs.append((dist, i, j))
        used_t, used_d = set(), set()
        for dist, i, j in sorted(pairs):
            if i in used_t or j in used_d:
                continue
            used_t.add(i)
            used_d.add(j)
            self._match(self.tracks[i], detections[j], t, frame)
        for j, det in enumerate(detections):
            if j not in used_d:
                self.tracks.append(self._new(det, t, frame))
        crossed = []
        for i, tr in enumerate(self.tracks):
            if i not in used_t and tr["t"] != t:
                tr["missed"] += 1
            if not tr["counted"] and self._crosses(tr):
                tr["counted"] = True
                self.crossed += 1
                crossed.append(tr)
        moving = [tr["vx"] for tr in self.tracks if tr["hits"] >= 3]
        if moving:
            self.velocity = float(np.median(moving))
        self.tracks = [tr for tr in self.tracks if tr["missed"] <= self.max_missed]
        return crossed

    def _crosses(self, tr):
        a, b = tr["prev_cx"] - self.line, tr["cx"] - self.line
        return (a < 0 <= b) if self.direction > 0 else (a > 0 >= b)

    def _new(self, det, t, frame):
        tr = {"id": self.next_id, "cx": det["centroid"][0], "cy": det["centroid"][1], "prev_cx": det["centroid"][0], "vx": self.velocity, "t": t, "t0": t, "hits": 1, "missed": 0, "counted": False, "views": [], "sizes": [], "box": det["box"]}
        self.next_id += 1
        self._observe(tr, det, frame)
        return tr

    def _match(self, tr, det, t, frame):
        dt = t - tr["t"]
        if dt > 0:
            vx = (det["centroid"][0] - tr["cx"]) / dt
            tr["vx"] = vx if tr["hits"] < 2 else 0.6 * tr["vx"] + 0.4 * vx
        tr["prev_cx"] = tr["cx"]
        tr["cx"], tr["cy"] = det["centroid"]
        tr["t"] = t
        tr["hits"] += 1
        tr["missed"] = 0
        tr["box"] = det["box"]
        self._observe(tr, det, frame)

    def _observe(self, tr, det, frame):
        if det["edge"]:
            return
        tr["sizes"].append(det["diameter_mm"])
        if len(tr["views"]) < self.max_views and (tr["hits"] - 1) % self.views_every == 0 and frame is not None:
            tr["views"].append(square_crop(frame, det["box"]))
