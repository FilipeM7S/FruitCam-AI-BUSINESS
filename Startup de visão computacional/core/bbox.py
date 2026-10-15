import numpy as np
from scipy import ndimage


def _otsu_threshold(gray):
    hist, edges = np.histogram(gray, bins=256, range=(0, 256))
    centers = (edges[:-1] + edges[1:]) / 2
    w1 = np.cumsum(hist)
    w2 = np.cumsum(hist[::-1])[::-1]
    m1 = np.cumsum(hist * centers) / np.clip(w1, 1, None)
    m2 = (np.cumsum((hist * centers)[::-1])[::-1]) / np.clip(w2, 1, None)
    variance = w1[:-1] * w2[1:] * (m1[:-1] - m2[1:]) ** 2
    return centers[:-1][np.argmax(variance)]


def detect_bbox(image, bg_is_light=True):
    gray = np.array(image.convert("L"), dtype=np.float32)
    threshold = _otsu_threshold(gray)
    mask = gray < threshold if bg_is_light else gray > threshold
    labeled, n = ndimage.label(mask)
    if n == 0:
        h, w = gray.shape
        return (0, 0, w - 1, h - 1)
    sizes = ndimage.sum(mask, labeled, range(1, n + 1))
    largest = np.argmax(sizes) + 1
    ys, xs = np.where(labeled == largest)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return (x0, y0, x1, y1)