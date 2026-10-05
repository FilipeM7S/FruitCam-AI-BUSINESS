import time
import uuid
from functools import lru_cache

import cv2
import numpy as np
import torch
from django.conf import settings
from PIL import Image, ImageOps

from Bbox import detect_bbox
from belt.classify import GOOD, CropClassifier

FORMATS = {"JPEG", "PNG", "WEBP"}
CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class UploadRejected(Exception):
    pass


@lru_cache(maxsize=1)
def get_model():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    classifier = CropClassifier(settings.MODEL_PATH, device)
    return classifier, classifier.classes, device


def save_upload(f):
    if f.size > settings.MAX_UPLOAD_BYTES:
        raise UploadRejected("file_too_large")
    if f.content_type not in CONTENT_TYPES:
        raise UploadRejected("unsupported_type")
    try:
        with Image.open(f) as im:
            if im.format not in FORMATS:
                raise UploadRejected("unsupported_type")
            if im.width * im.height > settings.MAX_IMAGE_PIXELS:
                raise UploadRejected("image_too_large")
            im.load()
            image = ImageOps.exif_transpose(im).convert("RGB")
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise UploadRejected("invalid_image")
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.png"
    image.save(settings.UPLOAD_DIR / name, "PNG", compress_level=1)
    return name, image


def fruit_crop(image, box, margin=0.15):
    x0, y0, x1, y1 = box
    side = max(x1 - x0 + 1, y1 - y0 + 1) * (1 + margin)
    cx, cy = (x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2
    side = min(side, image.width, image.height)
    left = min(max(cx - side / 2, 0), image.width - side)
    top = min(max(cy - side / 2, 0), image.height - side)
    crop = image.crop((round(left), round(top), round(left + side), round(top + side)))
    return cv2.cvtColor(np.asarray(crop), cv2.COLOR_RGB2BGR)


def classify_photo(classifier, image):
    box = detect_bbox(image)
    p = classifier.probs([fruit_crop(image, box)])[0]
    k = int(p.argmax())
    confidence = float(p[k])
    label = classifier.classes[k]
    return {
        "label": label,
        "is_good": label in GOOD,
        "deformity_type": None if label in GOOD else label,
        "confidence": confidence,
        "probs": {c: float(v) for c, v in zip(classifier.classes, p)},
        "needs_review": classifier.needs_review(confidence),
        "box": list(box),
    }


def run_model(path, image):
    classifier = get_model()[0]
    start = time.perf_counter()
    result = classify_photo(classifier, image)
    result["inference_ms"] = (time.perf_counter() - start) * 1000
    result["model_version"] = classifier.version
    return result
