import argparse
import os


def yolo_to_pixels(cx, cy, w, h, img_w, img_h):
    x0 = (cx - w / 2) * img_w
    y0 = (cy - h / 2) * img_h
    x1 = (cx + w / 2) * img_w
    y1 = (cy + h / 2) * img_h
    return max(0, x0), max(0, y0), min(img_w, x1), min(img_h, y1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("images_dir")
    parser.add_argument("labels_dir")
    parser.add_argument("--classes", type=int, nargs="+", default=[4, 5])
    args = parser.parse_args()

    from PIL import Image

    sizes = []
    for label_file in sorted(os.listdir(args.labels_dir)):
        if not label_file.endswith(".txt"):
            continue
        stem = label_file[:-4]
        image_path = os.path.join(args.images_dir, stem + ".jpg")
        if not os.path.exists(image_path):
            continue
        img_w, img_h = Image.open(image_path).size
        with open(os.path.join(args.labels_dir, label_file)) as f:
            for line in f:
                parts = line.split()
                if not parts:
                    continue
                cls_id = int(parts[0])
                if cls_id not in args.classes:
                    continue
                cx, cy, w, h = map(float, parts[1:5])
                x0, y0, x1, y1 = yolo_to_pixels(cx, cy, w, h, img_w, img_h)
                sizes.append(min(x1 - x0, y1 - y0))

    total = len(sizes)
    print(f"total boxes: {total}")
    for t in [16, 24, 32, 48, 64, 80, 96, 128]:
        kept = sum(1 for s in sizes if s >= t)
        pct = 100 * kept / total if total else 0
        print(f"min_size={t:>4}: keeps {kept}/{total} ({pct:.1f}%)")


if __name__ == "__main__":
    main()