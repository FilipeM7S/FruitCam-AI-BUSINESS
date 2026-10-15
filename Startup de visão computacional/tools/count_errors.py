import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import eval_belt
from belt.detect import BeltDetector
from belt.pipeline import BeltPipeline
from belt.simulate import SimulatedBelt
from belt.track import Tracker
from belt.stats import wilson

OUT = ROOT / "docs" / "reports" / "counting"
OVERLAPS = [("espaçamento normal", 18.0, 2.0), ("sobreposição até 10 mm", -10.0, 6.0), ("sobreposição até 25 mm", -25.0, 6.0), ("sobreposição até 40 mm", -40.0, 6.0), ("sobreposição até 40 mm, 10 por segundo", -40.0, 10.0)]


def run(sim, seconds, **detector):
    truth, sizes = {}, []

    def decide(track):
        fruit = sim.truth_at(track["cx"], track["cy"])
        truth[track["id"]] = None if fruit is None else fruit["id"]
        if fruit is not None and track["sizes"]:
            sizes.append(float(sorted(track["sizes"])[len(track["sizes"]) // 2]) / (2 * (fruit["area_mm2"] / 3.141592653589793) ** 0.5))
        return {"label": "boa", "confidence": None, "probs": {}, "views": len(track["views"]), "size_mm": None, "needs_review": True}

    tracking = {k: detector.pop(k) for k in ("merge", "merge_window") if k in detector}
    pipe = BeltPipeline(decide, sim.px_per_mm, sim.width, rows=(sim.top, sim.bottom), detector=BeltDetector(sim.px_per_mm, rows=(sim.top, sim.bottom), **detector))
    pipe.tracker = Tracker(pipe.line_x, 1, **tracking)
    started, counted = time.perf_counter(), 0
    frames = int(seconds * sim.fps)
    for _ in range(frames):
        t, frame = sim.read()
        counted += len(pipe.process(t, frame)[0])
    crossed = sim.next_id - sum(1 for f in sim.fruits if f["x"] < pipe.line_x)
    seen = [v for v in truth.values() if v is not None]
    return {
        "crossed": int(crossed),
        "counted": counted,
        "error": (counted - crossed) / crossed if crossed else None,
        "double_counts": len(seen) - len(set(seen)),
        "double_count_rate_ci95": wilson(len(seen) - len(set(seen)), int(crossed)),
        "counted_without_a_fruit_under_them": len(truth) - len(seen),
        "frames_with_a_cut": pipe.detector.splits,
        "frames_with_a_bridge": pipe.detector.bridges,
        "counts_merged_by_the_tracker": pipe.tracker.merged,
        "size_ratio_median": float(sorted(sizes)[len(sizes) // 2]) if sizes else None,
        "frames_per_second": frames / (time.perf_counter() - started),
    }


def real_fruit(minutes, seed=eval_belt.SEED, **detector):
    pool, _, _ = eval_belt.test_pool_v3()
    return run(SimulatedBelt(rate_per_s=2.0, mix=(1, 1, 1), seed=seed, crops=pool), 60 * minutes, **detector)


def drawn(gap_mm, rate, seconds, seed=6, **detector):
    return run(SimulatedBelt(rate_per_s=rate, seed=seed, gap_mm=gap_mm), seconds, **detector)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=8.0)
    parser.add_argument("--seconds", type=float, default=120.0)
    parser.add_argument("--variants", default=json.dumps({"atual": {}, "com ponte": {"bridge": 0.6}}))
    parser.add_argument("--skip-real", action="store_true")
    parser.add_argument("--out", default=str(OUT / "counting.json"))
    args = parser.parse_args()
    variants = json.loads(args.variants)
    result = {"what": "counting on the simulated belt; nothing here was measured on a real belt", "variants": variants, "drawn_fruit": {}, "real_fruit_crops": {}}
    for name, settings in variants.items():
        result["drawn_fruit"][name] = {}
        for label, gap, rate in OVERLAPS:
            result["drawn_fruit"][name][label] = {"gap_mm": gap, "rate_per_s": rate, "seconds": args.seconds, **drawn(gap, rate, args.seconds, **settings)}
            r = result["drawn_fruit"][name][label]
            print(f"{name:22s} drawn  {label:40s} crossed {r['crossed']:5d} counted {r['counted']:5d} ({100 * r['error']:+.1f}%) doubles {r['double_counts']} cuts {r['frames_with_a_cut']} bridges {r['frames_with_a_bridge']} merged {r['counts_merged_by_the_tracker']} {r['frames_per_second']:.0f} fps", flush=True)
        if not args.skip_real:
            result["real_fruit_crops"][name] = {"minutes": args.minutes, "seed": eval_belt.SEED, **real_fruit(args.minutes, **settings)}
            r = result["real_fruit_crops"][name]
            print(f"{name:22s} real   {args.minutes:g} min crossed {r['crossed']} counted {r['counted']} ({100 * r['error']:+.2f}%) doubles {r['double_counts']} bridges {r['frames_with_a_bridge']} merged {r['counts_merged_by_the_tracker']} size ratio {r['size_ratio_median']:.3f} {r['frames_per_second']:.0f} fps", flush=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
