import math

import cv2
import numpy as np

CLASSES = ("boa", "baixa_qualidade", "podre")
LOOKS = {
    "boa": {"body": ((40, 50, 215), (60, 160, 245)), "length_mm": (48, 62)},
    "baixa_qualidade": {"body": ((60, 170, 140), (90, 205, 190)), "length_mm": (32, 46)},
    "podre": {"body": ((30, 55, 95), (45, 80, 125)), "length_mm": (42, 58)},
}
BELT_BGR = (40, 46, 42)


class SimulatedBelt:
    def __init__(self, width=960, height=540, fps=25.0, px_per_mm=1.6, speed_mm_s=250.0, rate_per_s=2.0, mix=(0.6, 0.25, 0.15), seed=0, margin_px=70, gap_mm=18.0, crops=None):
        self.width, self.height, self.fps = width, height, fps
        self.px_per_mm = px_per_mm
        self.speed = speed_mm_s * px_per_mm
        self.rate = rate_per_s
        self.mix = np.asarray(mix, float) / np.sum(mix)
        self.rng = np.random.default_rng(seed)
        self.top, self.bottom = margin_px, height - margin_px
        self.gap = gap_mm * px_per_mm
        self.crops = crops
        self.fruits = []
        self.next_id = 0
        self.frame_index = 0
        self.next_arrival = self.rng.exponential(1 / rate_per_s) if rate_per_s > 0 else math.inf
        self.texture = self._texture()

    def _texture(self):
        h, w = self.bottom - self.top, self.width * 2
        noise = self.rng.normal(0, 4, (h, w // 4, 1)).repeat(4, axis=1)
        base = np.full((h, w, 3), BELT_BGR, float) + noise
        for x in range(0, w, 320):
            base[:, x:x + 6] -= 14
        return np.clip(base, 0, 255).astype(np.uint8)

    def _sprite(self, label):
        if self.crops is not None:
            pool = self.crops[label]
            crop = pool[self.rng.integers(len(pool))]
            mask = None
            if isinstance(crop, tuple):
                crop, mask = crop
            length = self.rng.uniform(*LOOKS[label]["length_mm"])
            fill = 1.0
            if mask is not None:
                ys, xs = np.nonzero(mask)
                if len(xs):
                    fill = max(xs.max() - xs.min() + 1, ys.max() - ys.min() + 1) / max(mask.shape)
            side = max(int(round(length * self.px_per_mm / max(fill, 0.2))), 8)
            patch = cv2.resize(crop, (side, side), interpolation=cv2.INTER_AREA)
            if mask is not None:
                alpha = cv2.resize(mask.astype(np.float32), (side, side), interpolation=cv2.INTER_LINEAR)
                return patch, cv2.GaussianBlur(alpha, (3, 3), 0), length
            yy, xx = np.mgrid[0:side, 0:side]
            alpha = (((xx - side / 2) / (side / 2)) ** 2 + ((yy - side / 2) / (side / 2)) ** 2 <= 0.92).astype(float)
            return patch, cv2.GaussianBlur(alpha, (5, 5), 0), length
        look = LOOKS[label]
        length = self.rng.uniform(*look["length_mm"])
        a = length * self.px_per_mm / 2
        b = a * self.rng.uniform(0.62, 0.78)
        nut = a * 0.45
        side = int(2 * (a + nut) + 12)
        c = side // 2
        lo, hi = (np.array(v, float) for v in look["body"])
        body = lo + (hi - lo) * self.rng.uniform(0, 1)
        sprite = np.zeros((side, side, 3), float)
        alpha = np.zeros((side, side), float)
        mask = np.zeros((side, side), np.uint8)
        cv2.ellipse(mask, (c, c), (int(a), int(b)), 0, 0, 360, 255, -1)
        yy, xx = np.mgrid[0:side, 0:side]
        shade = np.clip(1.15 - 0.55 * np.hypot((xx - c + a * 0.3) / a, (yy - c + b * 0.35) / b), 0.55, 1.2)
        tex = self.rng.normal(0, 6, (side, side))
        sprite[:] = body
        sprite *= shade[..., None]
        sprite += tex[..., None]
        if label == "podre":
            for _ in range(self.rng.integers(3, 7)):
                r = int(self.rng.uniform(0.12, 0.3) * b)
                p = (int(c + self.rng.uniform(-0.6, 0.6) * a), int(c + self.rng.uniform(-0.5, 0.5) * b))
                spot = np.zeros_like(mask)
                cv2.circle(spot, p, r, 255, -1)
                sprite[spot > 0] *= 0.45
        alpha[mask > 0] = 1
        nut_mask = np.zeros_like(mask)
        cv2.ellipse(nut_mask, (int(c + a + nut * 0.55), c), (int(nut * 0.75), int(nut * 0.45)), 20, 0, 360, 255, -1)
        sprite[nut_mask > 0] = (70, 85, 95)
        alpha[nut_mask > 0] = 1
        angle = self.rng.uniform(0, 360)
        rot = cv2.getRotationMatrix2D((c, c), angle, 1.0)
        sprite = cv2.warpAffine(np.clip(sprite, 0, 255), rot, (side, side), flags=cv2.INTER_LINEAR)
        alpha = cv2.warpAffine(alpha, rot, (side, side), flags=cv2.INTER_LINEAR)
        alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
        return sprite.astype(np.uint8), alpha, length

    def _spawn(self, t):
        label = CLASSES[self.rng.choice(len(CLASSES), p=self.mix)]
        sprite, alpha, length = self._sprite(label)
        half = sprite.shape[0] / 2
        for _ in range(12):
            y = self.rng.uniform(self.top + half + 4, self.bottom - half - 4)
            x = -half
            if all(math.hypot(f["x"] - x, f["y"] - y) > f["half"] + half + self.gap for f in self.fruits):
                fruit = {"id": self.next_id, "label": label, "length_mm": length, "area_mm2": float(alpha.sum()) / self.px_per_mm ** 2, "x": x, "y": y, "half": half, "t0": t, "x0": x, "sprite": sprite, "alpha": alpha, "shadow": cv2.GaussianBlur(alpha, (0, 0), 3) * 0.35}
                self.fruits.append(fruit)
                self.next_id += 1
                return True
        return False

    def truth_at(self, x, y):
        best = min(self.fruits, key=lambda f: math.hypot(f["x"] - x, f["y"] - y), default=None)
        if best is None or math.hypot(best["x"] - x, best["y"] - y) > best["half"]:
            return None
        return best

    def crossing_time(self, fruit, line_x):
        return fruit["t0"] + (line_x - fruit["x0"]) / self.speed

    def read(self):
        t = self.frame_index / self.fps
        self.frame_index += 1
        while t >= self.next_arrival:
            if not self._spawn(self.next_arrival):
                self.next_arrival += 0.05
                continue
            self.next_arrival += self.rng.exponential(1 / self.rate)
        for f in self.fruits:
            f["x"] = f["x0"] + self.speed * (t - f["t0"])
        self.fruits = [f for f in self.fruits if f["x"] - f["half"] < self.width + 4]
        frame = np.zeros((self.height, self.width, 3), np.uint8)
        frame[:] = (24, 28, 26)
        offset = int(self.speed * t) % (self.texture.shape[1] // 2)
        frame[self.top:self.bottom] = self.texture[:, self.texture.shape[1] // 2 - offset:self.texture.shape[1] // 2 - offset + self.width]
        frame[self.top - 8:self.top] = (70, 74, 72)
        frame[self.bottom:self.bottom + 8] = (70, 74, 72)
        for f in self.fruits:
            self._paste(frame, f)
        return t, frame

    def _paste(self, frame, f):
        s = f["sprite"].shape[0]
        x0, y0 = int(round(f["x"] - s / 2)), int(round(f["y"] - s / 2))
        fx0, fy0 = max(x0, 0), max(y0, 0)
        fx1, fy1 = min(x0 + s, self.width), min(y0 + s, self.height)
        if fx1 <= fx0 or fy1 <= fy0:
            return
        sx0, sy0 = fx0 - x0, fy0 - y0
        sx1, sy1 = sx0 + fx1 - fx0, sy0 + fy1 - fy0
        a = f["alpha"][sy0:sy1, sx0:sx1, None]
        shadow = f["shadow"][sy0:sy1, sx0:sx1, None]
        region = frame[fy0:fy1, fx0:fx1].astype(float)
        region *= 1 - shadow
        region = region * (1 - a) + f["sprite"][sy0:sy1, sx0:sx1] * a
        frame[fy0:fy1, fx0:fx1] = np.clip(region, 0, 255).astype(np.uint8)
