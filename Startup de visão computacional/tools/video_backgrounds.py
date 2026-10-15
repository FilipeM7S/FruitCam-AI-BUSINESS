import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import cv2
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
STORE = Path(os.environ.get("FRUITCAM_DATA_STORE") or Path.home() / "FruitCamData")
OUT = STORE / "video_backgrounds"
VIDEOS = ROOT / "data" / "external"
SHORT_SIDE = 360
REGIONS = {
    "train": [
        ("usda_line_videos/raw/potato_0921.webm", 0.0, 9.0, 0.00, 0.30, 0.88, 1.00),
        ("usda_line_videos/raw/potato_0918.webm", 0.0, 5.5, 0.26, 0.56, 0.60, 1.00),
        ("usda_line_videos/raw/potato_0919.webm", 0.0, 2.6, 0.28, 0.62, 0.72, 0.98),
        ("usda_line_videos/raw/potato_0920.webm", 0.0, 10.5, 0.28, 0.62, 0.72, 0.98),
        ("usda_line_videos/raw/potato_0912.webm", 0.0, 5.0, 0.04, 0.42, 0.62, 0.72),
        ("usda_line_videos/raw/potato_0922.webm", 0.0, 8.7, 0.06, 0.74, 0.50, 0.92),
    ],
    "test": [
        ("usda_line_videos/raw/citrus_packing_facility.webm", 122.0, 130.0, 0.04, 0.56, 0.62, 1.00),
        ("usda_line_videos/raw/citrus_packing_facility.webm", 133.0, 147.0, 0.00, 0.26, 0.46, 0.72),
        ("apple_grading_video/raw/apple_grading.webm", 5.0, 12.0, 0.50, 0.12, 1.00, 0.92),
    ],
}


def frames(video, start, end, box, target, rate=2.0):
    probe = cv2.VideoCapture(str(video))
    width, height = int(probe.get(cv2.CAP_PROP_FRAME_WIDTH)), int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
    probe.release()
    x0, y0, x1, y1 = box
    w, h = int((x1 - x0) * width) // 2 * 2, int((y1 - y0) * height) // 2 * 2
    scale = SHORT_SIDE / min(w, h)
    size = f"{int(w * scale) // 2 * 2}:{int(h * scale) // 2 * 2}"
    chain = f"fps={rate},crop={w}:{h}:{int(x0 * width)}:{int(y0 * height)},scale={size}:flags=area"
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", f"{start}", "-t", f"{end - start}", "-i", str(video), "-vf", chain, "-q:v", "3", str(target) + "_%03d.jpg"]
    subprocess.run(command, check=True)


def build(out=OUT):
    summary = {}
    for split, regions in REGIONS.items():
        folder = Path(out) / split
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.jpg"):
            old.unlink()
        for index, (name, start, end, *box) in enumerate(regions):
            video = VIDEOS / name
            if not video.exists():
                raise SystemExit(f"{video} is missing; run python scripts/fetch_datasets.py first")
            frames(video, start, end, box, folder / f"{Path(name).stem}_{index}")
        files = sorted(folder.glob("*.jpg"))
        summary[split] = {"pictures": len(files), "clips": sorted({f.name.rsplit("_", 2)[0] for f in files}), "bytes": sum(f.stat().st_size for f in files)}
    (Path(out) / "summary.json").write_text(json.dumps({"short_side_px": SHORT_SIDE, "regions": {k: [list(r) for r in v] for k, v in REGIONS.items()}, "built": summary}, indent=1) + chr(10), encoding="utf-8")
    return summary


def bank(split, out=OUT):
    return [cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB) for path in sorted((Path(out) / split).glob("*.jpg"))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    for split, info in build(args.out).items():
        print(f"{split}: {info['pictures']} pictures from {info['clips']} ({info['bytes'] / 1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())
