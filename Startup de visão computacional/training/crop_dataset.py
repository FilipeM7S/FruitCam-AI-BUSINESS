import argparse
import os
import random
from PIL import Image

CLASS_NAMES = {0: "tree", 1: "flower", 2: "premature", 3: "unripe", 4: "ripe", 5: "spoilt"}


def yolo_to_pixels(cx, cy, w, h, img_w, img_h):
    x0 = (cx - w / 2) * img_w
    y0 = (cy - h / 2) * img_h
    x1 = (cx + w / 2) * img_w
    y1 = (cy + h / 2) * img_h
    return max(0, int(x0)), max(0, int(y0)), min(img_w, int(x1)), min(img_h, int(y1))


def crop_dataset(images_dir, labels_dir, out_dir, class_map, val_frac=0.15, seed=0, min_size=96):
    random.seed(seed)
    counts = {name: 0 for name in class_map.values()}
    skipped_small = 0
    total_boxes = 0
    for label_file in sorted(os.listdir(labels_dir)):
        if not label_file.endswith(".txt"):
            continue
        stem = label_file[:-4]
        image_path = os.path.join(images_dir, stem + ".jpg")
        if not os.path.exists(image_path):
            continue
        image = Image.open(image_path).convert("RGB")
        img_w, img_h = image.size
        with open(os.path.join(labels_dir, label_file)) as f:
            lines = [l.strip() for l in f if l.strip()]
        for i, line in enumerate(lines):
            parts = line.split()
            cls_id = int(parts[0])
            if cls_id not in class_map:
                continue
            cx, cy, w, h = map(float, parts[1:5])
            x0, y0, x1, y1 = yolo_to_pixels(cx, cy, w, h, img_w, img_h)
            total_boxes += 1
            if x1 - x0 < min_size or y1 - y0 < min_size:
                skipped_small += 1
                continue
            crop = image.crop((x0, y0, x1, y1))
            class_name = class_map[cls_id]
            split = "val" if random.random() < val_frac else "train"
            d = os.path.join(out_dir, split, class_name)
            os.makedirs(d, exist_ok=True)
            crop.save(os.path.join(d, f"{stem}_{i}.jpg"))
            counts[class_name] += 1
    return counts, skipped_small, total_boxes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("images_dir")
    parser.add_argument("labels_dir")
    parser.add_argument("out_dir")
    parser.add_argument("--min-size", type=int, default=96)
    args = parser.parse_args()
    class_map = {5: "podre", 4: "nao_podre"}
    counts, skipped_small, total_boxes = crop_dataset(
        args.images_dir, args.labels_dir, args.out_dir, class_map, min_size=args.min_size,
    )
    pct = 100 * skipped_small / total_boxes if total_boxes else 0
    print("counts:", counts)
    print(f"skipped_small: {skipped_small}/{total_boxes} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
