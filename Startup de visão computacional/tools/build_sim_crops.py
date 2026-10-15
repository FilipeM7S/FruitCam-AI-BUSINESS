import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from training.train_belt import CLASSES, attach_masks, load_crops, tree_as_five

OUT = ROOT / "assets" / "media_src" / "belt_crops"
PER_CLASS = 36
SIDE = 128
SEED = 7
TEXTURE_MAX = 4.0


def sharpen(rgba):
    rgb = rgba[..., :3].astype(np.float32)
    soft = cv2.GaussianBlur(rgb, (0, 0), 1.6)
    rgba[..., :3] = np.clip(rgb + 0.7 * (rgb - soft), 0, 255).astype(np.uint8)
    return rgba


def texture(rgba):
    gray = cv2.cvtColor(rgba[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
    inside = cv2.erode((rgba[..., 3] > 127).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    lap = np.abs(cv2.Laplacian(cv2.GaussianBlur(gray, (3, 3), 0), cv2.CV_32F))
    return float(lap[inside].mean()) if inside.any() else float("inf")


def main():
    items = load_crops(ROOT / "datasets" / "cashew" / "images", ROOT / "datasets" / "cashew" / "labels", 32, 0.15, 0, tree_as_five(ROOT / "datasets" / "cashew" / "labels"))
    attach_masks(items)
    rng = np.random.default_rng(SEED)
    shutil.rmtree(OUT, ignore_errors=True)
    sources = []
    for k, name in enumerate(CLASSES):
        pool = []
        for it in items:
            if it["label"] != k or it["mask_method"] != "grabcut":
                continue
            mask = it["mask"].astype(np.uint8)
            share = float(mask.mean())
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            hull = cv2.contourArea(cv2.convexHull(max(contours, key=cv2.contourArea))) if contours else 0
            solidity = float(mask.sum()) / hull if hull else 0
            if 0.25 <= share <= 0.85 and solidity >= 0.92:
                pool.append(it)
        smooth = []
        for it in pool:
            rgb = np.asarray(it["image"])
            mask = cv2.resize(it["mask"].astype(np.uint8), (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
            rgba = cv2.resize(np.dstack([cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), mask * 255]), (SIDE, SIDE), interpolation=cv2.INTER_LANCZOS4 if SIDE > rgb.shape[0] else cv2.INTER_AREA)
            if texture(rgba) < TEXTURE_MAX:
                smooth.append((it, sharpen(rgba)))
        chosen = [smooth[i] for i in rng.permutation(len(smooth))[:PER_CLASS]]
        (OUT / name).mkdir(parents=True, exist_ok=True)
        for it, rgba in chosen:
            file = f"{it['key'].replace(':', '__')}.png"
            cv2.imwrite(str(OUT / name / file), rgba, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            sources.append({"file": f"{name}/{file}", "class": name, "photo": f"datasets/cashew/images/{it['photo']}.jpg", "dataset": "cashew_makerere"})
        print(f"{name:16s} {len(chosen):3d} chosen; {len(pool):4d} with a clean, compact mask, {len(smooth):4d} of them smooth (fruit, not foliage)")
    meta = {
        "what": "Recortes de cajus de fotos reais, usados como frutas da esteira simulada (página Linha).",
        "dataset": "cashew_makerere",
        "crops": sources,
    }
    (OUT / "sources.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(sources)} crops, {sum(p.stat().st_size for p in OUT.rglob('*.png')) / 1024:.0f} KB in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
