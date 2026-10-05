import json
import subprocess
import sys
from pathlib import Path

import cv2
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from belt.classify import TruthDecider
from belt.pipeline import BeltPipeline
from belt.simulate import SimulatedBelt

OUT = ROOT / "media_src" / "video"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SECONDS = 12
WARMUP = 6


def encode(frames, fps, path, args):
    h, w = frames[0].shape[:2]
    proc = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", *args, "-an", "-map_metadata", "-1", str(path)], stdin=subprocess.PIPE)
    for f in frames:
        proc.stdin.write(f.tobytes())
    proc.stdin.close()
    assert proc.wait() == 0, path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    belt = SimulatedBelt(rate_per_s=3.2, mix=(0.6, 0.25, 0.15), seed=7)
    pipe = BeltPipeline(TruthDecider(belt), belt.px_per_mm, belt.width, rows=(belt.top, belt.bottom), camera="linha-1", stamp="SIMULAÇÃO · rótulos da simulação")
    frames, truth = [], 0
    total = int((WARMUP + SECONDS) * belt.fps)
    for i in range(total):
        t, frame = belt.read()
        passages, image = pipe.process(t, frame, draw=i >= WARMUP * belt.fps)
        if image is not None:
            frames.append(image)
            truth += len(passages)
    encode(frames, belt.fps, OUT / "belt-sim.webm", ["-c:v", "libvpx-vp9", "-crf", "38", "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", "-pix_fmt", "yuv420p"])
    encode(frames, belt.fps, OUT / "belt-sim.mp4", ["-c:v", "libx264", "-crf", "28", "-preset", "veryslow", "-tune", "animation", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    cv2.imwrite(str(OUT / "belt-sim-poster.png"), frames[len(frames) // 2])
    meta = {"seconds": SECONDS, "fps": belt.fps, "width": belt.width, "height": belt.height, "counted_in_clip": truth, "seed": 7}
    (OUT / "belt-sim.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    for name in ("belt-sim.webm", "belt-sim.mp4", "belt-sim-poster.png"):
        print(f"{name:22s} {(OUT / name).stat().st_size:9d} B")
    print(meta)


if __name__ == "__main__":
    main()
