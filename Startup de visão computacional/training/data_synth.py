
import os
import random
from PIL import Image


def make_synthetic_dataset(root, classes, n_per_class=24, img_size=64, seed=0):
    random.seed(seed)
    for split, count in [("train", n_per_class), ("val", max(4, n_per_class // 4))]:
        for cls_idx, cls in enumerate(classes):
            d = os.path.join(root, split, cls)
            os.makedirs(d, exist_ok=True)
            base = (cls_idx * 90) % 256
            for i in range(count):
                color = (base, (base + i * 7) % 256, (base + i * 13) % 256)
                img = Image.new("RGB", (img_size, img_size), color)
                img.save(os.path.join(d, f"{cls}_{i}.png"))


if __name__ == "__main__":
    make_synthetic_dataset("data_synthetic", ["W180", "W320", "W400"])