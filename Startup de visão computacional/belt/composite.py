import cv2
import numpy as np

TRAIN_BELTS = {
    "cinza-escuro": (52, 54, 56),
    "cinza-medio": (108, 110, 112),
    "preto": (24, 25, 27),
    "verde-escuro": (40, 74, 52),
    "branco": (212, 214, 210),
    "bege": (176, 160, 128),
}
HELD_OUT_BELTS = {
    "azul": (38, 84, 150),
    "azul-claro": (92, 140, 190),
}
MASK_SIDE = 160


def fruit_mask(crop_rgb, inner):
    h, w = crop_rgb.shape[:2]
    scale = min(1.0, MASK_SIDE / max(h, w))
    small = cv2.resize(crop_rgb, (max(int(w * scale), 8), max(int(h * scale), 8)), interpolation=cv2.INTER_AREA) if scale < 1 else crop_rgb
    sh, sw = small.shape[:2]
    x0, y0, x1, y1 = (int(round(v * scale)) for v in inner)
    x0, y0 = max(x0, 1), max(y0, 1)
    x1, y1 = min(x1, sw - 2), min(y1, sh - 2)
    ellipse = np.zeros((sh, sw), np.uint8)
    cv2.ellipse(ellipse, ((x0 + x1) // 2, (y0 + y1) // 2), (max((x1 - x0) // 2, 1), max((y1 - y0) // 2, 1)), 0, 0, 360, 1, -1)
    method = "ellipse"
    mask = ellipse
    if x1 - x0 >= 10 and y1 - y0 >= 10:
        gc = np.full((sh, sw), cv2.GC_BGD, np.uint8)
        gc[y0:y1, x0:x1] = cv2.GC_PR_BGD
        gc[ellipse == 1] = cv2.GC_PR_FGD
        cv2.ellipse(gc, ((x0 + x1) // 2, (y0 + y1) // 2), (max((x1 - x0) // 4, 1), max((y1 - y0) // 4, 1)), 0, 0, 360, cv2.GC_FGD, -1)
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
            cut = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
            cut = cv2.morphologyEx(cut, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            n, labels, stats, _ = cv2.connectedComponentsWithStats(cut, connectivity=8)
            if n > 1:
                biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
                cut = (labels == biggest).astype(np.uint8)
                flood = cut.copy()
                cv2.floodFill(flood, np.zeros((sh + 2, sw + 2), np.uint8), (0, 0), 1)
                cut = cut | (1 - flood)
                share = cut.sum() / max((x1 - x0) * (y1 - y0), 1)
                if 0.2 <= share <= 0.98:
                    mask, method = cut, "grabcut"
        except cv2.error:
            pass
    if scale < 1:
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    return mask.astype(np.uint8), method


def belt_background(h, w, rng, palette):
    name = list(palette)[rng.integers(len(palette))]
    base = np.array(palette[name], np.float32) * rng.uniform(0.82, 1.15) + rng.normal(0, 6, 3)
    bg = np.empty((h, w, 3), np.float32)
    bg[:] = base
    bg += rng.normal(0, rng.uniform(2, 7), (h, w, 1))
    weave = rng.uniform(0, 4)
    period = rng.uniform(3, 7)
    angle = rng.uniform(0, np.pi)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    bg += (weave * np.sin((xx * np.cos(angle) + yy * np.sin(angle)) * 2 * np.pi / period))[..., None]
    gx, gy = rng.uniform(-0.25, 0.25, 2)
    light = 1 + gx * (xx / max(w - 1, 1) - 0.5) + gy * (yy / max(h - 1, 1) - 0.5)
    bg *= light[..., None]
    if rng.random() < 0.25:
        x = int(rng.integers(0, w))
        bg[:, x:x + max(1, w // 40)] *= rng.uniform(0.75, 0.9)
    return np.clip(bg, 0, 255), name


def composite(crop_rgb, mask, rng, palette=TRAIN_BELTS):
    h, w = crop_rgb.shape[:2]
    bg, name = belt_background(h, w, rng, palette)
    alpha = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), max(0.6, min(h, w) / 160))
    scale = rng.uniform(0.85, 1.08)
    dx, dy = rng.uniform(-0.05, 0.05, 2) * (w, h)
    m = cv2.getRotationMatrix2D((w / 2, h / 2), 0, scale)
    m[:, 2] += (dx, dy)
    fruit = cv2.warpAffine(crop_rgb.astype(np.float32), m, (w, h), borderMode=cv2.BORDER_REFLECT)
    alpha = cv2.warpAffine(alpha, m, (w, h))
    shift = np.float32([[1, 0, w * rng.uniform(0.01, 0.05)], [0, 1, h * rng.uniform(0.02, 0.06)]])
    shadow = cv2.GaussianBlur(cv2.warpAffine(alpha, shift, (w, h)), (0, 0), max(1.0, min(h, w) / 30)) * rng.uniform(0.2, 0.45)
    bg *= (1 - shadow)[..., None]
    out = fruit * alpha[..., None] + bg * (1 - alpha[..., None])
    if rng.random() < 0.3:
        k = int(rng.integers(2, 6))
        out = cv2.filter2D(out, -1, np.full((1, k), 1 / k, np.float32))
    return np.clip(out, 0, 255).astype(np.uint8), name
