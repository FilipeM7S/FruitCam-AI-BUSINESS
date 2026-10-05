import time
from functools import lru_cache
from pathlib import Path

import cv2
import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .detect import BeltDetector
from .track import Tracker

COLORS = {"boa": (115, 158, 0), "nao_podre": (115, 158, 0), "baixa_qualidade": (0, 159, 230), "podre": (0, 94, 213), "indefinido": (167, 121, 204)}
NAMES = {"boa": "boa", "nao_podre": "não podre", "baixa_qualidade": "baixa qualidade", "podre": "podre", "indefinido": "revisar"}


@lru_cache(maxsize=4)
def font(size, bold=False):
    return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size)


class BeltPipeline:
    def __init__(self, decide, px_per_mm, width, line_frac=0.62, direction=1, rows=None, detector=None, tracker=None, camera="linha-1", stamp=None):
        self.decide = decide
        self.line_x = int(width * line_frac)
        self.detector = detector or BeltDetector(px_per_mm, rows=rows)
        self.tracker = tracker or Tracker(self.line_x, direction)
        self.camera = camera
        self.stamp = stamp
        self.recent = {}
        self.counts = {}
        self.frames = 0
        self.started = time.perf_counter()

    def process(self, t, frame, draw=False):
        detections, _ = self.detector.detect(frame)
        passages = []
        for track in self.tracker.update(t, detections, frame):
            result = self.decide(track)
            result.update({"t": t, "track_id": track["id"]})
            passages.append(result)
            shown = "indefinido" if result["needs_review"] else result["label"]
            self.counts[shown] = self.counts.get(shown, 0) + 1
            self.recent[track["id"]] = (t, result)
        self.frames += 1
        self.recent = {k: v for k, v in self.recent.items() if t - v[0] < 1.5}
        return passages, (self.draw(frame) if draw else None)

    def fps(self):
        return self.frames / max(time.perf_counter() - self.started, 1e-6)

    def draw(self, frame):
        out = frame.copy()
        h, w = out.shape[:2]
        for y in range(36, h, 18):
            cv2.line(out, (self.line_x, y), (self.line_x, y + 9), (240, 240, 240), 2)
        tags = []
        for tr in self.tracker.tracks:
            x0, y0, x1, y1 = tr["box"]
            if tr["id"] in self.recent:
                result = self.recent[tr["id"]][1]
                key = "indefinido" if result["needs_review"] else result["label"]
                color = COLORS.get(key, (220, 220, 220))
                cv2.rectangle(out, (x0, y0), (x1, y1), color, 3)
                text = NAMES.get(key, key) + (f" {result['confidence'] * 100:.0f}%" if result.get("confidence") is not None else "")
                tags.append((x0, y0, text, color))
            else:
                cv2.rectangle(out, (x0, y0), (x1, y1), (225, 225, 225), 1)
        cv2.rectangle(out, (0, 0), (w, 30), (30, 25, 20), -1)
        image = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
        pen = ImageDraw.Draw(image)
        small, bold = font(14), font(14, True)
        for x0, y0, text, color in tags:
            box = pen.textbbox((0, 0), text, font=bold)
            tw, th = box[2] - box[0], box[3] - box[1]
            top = max(y0 - th - 9, 31)
            pen.rectangle([x0, top, x0 + tw + 10, top + th + 8], fill=color[::-1])
            pen.text((x0 + 5, top + 2), text, font=bold, fill=(255, 255, 255))
        total = sum(self.counts.values())
        hud = f"{self.camera}   contadas {total}   " + "   ".join(f"{NAMES.get(k, k)} {v}" for k, v in sorted(self.counts.items()))
        pen.text((10, 7), hud, font=small, fill=(230, 242, 234))
        if self.stamp:
            box = pen.textbbox((0, 0), self.stamp, font=bold)
            tw, th = box[2] - box[0], box[3] - box[1]
            pen.rectangle([w - tw - 20, h - th - 18, w, h], fill=(20, 30, 25))
            pen.text((w - tw - 10, h - th - 12), self.stamp, font=bold, fill=(180, 232, 200))
        return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
