import argparse
import os
import random

from PIL import Image, ImageDraw, ImageFont

from crop_dataset import yolo_to_pixels

# WHY THIS SCRIPT EXISTS: size_test.py showed that the overwhelming majority of
# labeled boxes (>80% in the run you shared) are under 16px in their smaller
# dimension. crop_dataset.py's context-padding fix can turn those into usable
# training crops -- IF they are genuine small/distant fruit. If instead they are an
# annotation-tool artifact (e.g. accidental point-clicks, a coordinate-scale bug, a
# second low-res image source mixed into the same label set), padding them just
# manufactures label noise dressed up as data. This script doesn't decide that for
# you -- it makes a contact sheet of a random sample so you can look and decide,
# which is the only way to actually know. The native box is drawn in the crop so you
# can judge how much real fruit is visible vs. how much is padding.


def find_small_boxes(images_dir, labels_dir, classes, max_native_size):
    candidates = []
    for label_file in sorted(os.listdir(labels_dir)):
        if not label_file.endswith(".txt"):
            continue
        stem = label_file[:-4]
        image_path = os.path.join(images_dir, stem + ".jpg")
        if not os.path.exists(image_path):
            continue
        with open(os.path.join(labels_dir, label_file)) as f:
            lines = [l.strip() for l in f if l.strip()]
        for line in lines:
            parts = line.split()
            cls_id = int(parts[0])
            if cls_id not in classes:
                continue
            cx, cy, w, h = map(float, parts[1:5])
            candidates.append((image_path, cls_id, cx, cy, w, h))
    return candidates


def make_contact_sheet(images_dir, labels_dir, out_path, classes, max_native_size=16,
                        n=24, view_size=200, seed=0, cols=6):
    random.seed(seed)
    candidates = find_small_boxes(images_dir, labels_dir, classes, max_native_size)

    # filter to actually-small ones in pixel terms (candidates above are still in
    # normalized YOLO units; resolve to pixels per-image, since the same normalized
    # width means different pixel widths on different source images)
    small = []
    image_cache = {}
    for image_path, cls_id, cx, cy, w, h in candidates:
        if image_path not in image_cache:
            image_cache[image_path] = Image.open(image_path).convert("RGB")
        image = image_cache[image_path]
        img_w, img_h = image.size
        x0, y0, x1, y1 = yolo_to_pixels(cx, cy, w, h, img_w, img_h)
        native = min(x1 - x0, y1 - y0)
        if 0 < native <= max_native_size:
            small.append((image_path, cls_id, x0, y0, x1, y1, native))

    if not small:
        print(f"no boxes found with native size in (0, {max_native_size}]px")
        return None

    sample = random.sample(small, min(n, len(small)))
    print(f"found {len(small)} boxes <= {max_native_size}px, sampling {len(sample)}")

    rows = (len(sample) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * view_size, rows * view_size), (30, 30, 30))
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for idx, (image_path, cls_id, x0, y0, x1, y1, native) in enumerate(sample):
        image = image_cache[image_path]
        img_w, img_h = image.size
        cx_px, cy_px = (x0 + x1) / 2, (y0 + y1) / 2
        half = view_size / 2
        vx0, vy0 = max(0, cx_px - half), max(0, cy_px - half)
        vx1, vy1 = min(img_w, vx0 + view_size), min(img_h, vy0 + view_size)
        vx0, vy0 = max(0, vx1 - view_size), max(0, vy1 - view_size)
        tile = image.crop((int(vx0), int(vy0), int(vx1), int(vy1)))
        if tile.size != (view_size, view_size):
            padded = Image.new("RGB", (view_size, view_size), (30, 30, 30))
            padded.paste(tile, (0, 0))
            tile = padded

        draw = ImageDraw.Draw(tile)
        # native box location relative to this tile, drawn in bright red so you can
        # see exactly how much (or how little) of the tile is the labeled object
        rx0, ry0 = x0 - vx0, y0 - vy0
        rx1, ry1 = x1 - vx0, y1 - vy0
        draw.rectangle([rx0, ry0, rx1, ry1], outline=(255, 40, 40), width=2)
        label = f"cls={cls_id} {native}px"
        draw.rectangle([0, 0, len(label) * 6 + 6, 14], fill=(0, 0, 0))
        draw.text((3, 1), label, fill=(255, 255, 0), font=font)

        r, c = idx // cols, idx % cols
        sheet.paste(tile, (c * view_size, r * view_size))

    sheet.save(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("images_dir")
    parser.add_argument("labels_dir")
    parser.add_argument("--out", default="small_box_audit.jpg")
    parser.add_argument("--classes", type=int, nargs="+", default=[4, 5])
    parser.add_argument("--max-native-size", type=int, default=16,
                         help="Only sample boxes at or under this native pixel size.")
    parser.add_argument("--n", type=int, default=24)
    parser.add_argument("--view-size", type=int, default=200,
                         help="Size (px) of each tile's viewing window, for context.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    out_path = make_contact_sheet(
        args.images_dir, args.labels_dir, args.out, set(args.classes),
        max_native_size=args.max_native_size, n=args.n, view_size=args.view_size, seed=args.seed,
    )
    if out_path:
        print(f"contact sheet saved to: {out_path}")


if __name__ == "__main__":
    main()