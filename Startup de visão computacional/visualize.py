import argparse
import torch
from PIL import Image, ImageDraw
from infer import load_model, predict
from Bbox import detect_bbox

RED = (220, 30, 30)
GREEN = (30, 160, 30)


def annotate(image_path, checkpoint_path, bad_class, device=None, img_size=224, bg_is_light=True):
    device = device or torch.device("cpu")
    model, classes = load_model(checkpoint_path, device)
    if bad_class not in classes:
        raise ValueError(f"bad_class={bad_class!r} not in trained classes {classes}")

    label, confidence = predict(model, classes, image_path, device, img_size)
    image = Image.open(image_path).convert("RGB")
    x0, y0, x1, y1 = detect_bbox(image, bg_is_light=bg_is_light)

    color = RED if label == bad_class else GREEN
    draw = ImageDraw.Draw(image)
    line_width = max(2, image.width // 150)
    draw.rectangle([x0, y0, x1, y1], outline=color, width=line_width)
    draw.text((x0, max(0, y0 - 14)), f"{label} {confidence:.2f}", fill=color)
    return image, label, confidence, (x0, y0, x1, y1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--checkpoint", default="model.pt")
    parser.add_argument("--out", default="output.jpg")
    parser.add_argument("--bad-class", default="podre")
    parser.add_argument("--img-size", type=int, default=224)
    parser.add_argument("--dark-background", action="store_true")
    args = parser.parse_args()

    image, label, confidence, box = annotate(
        args.image, args.checkpoint, args.bad_class,
        img_size=args.img_size, bg_is_light=not args.dark_background,
    )
    image.save(args.out)
    print(f"{label} {confidence:.4f} box={box} saved_to={args.out}")


if __name__ == "__main__":
    main()