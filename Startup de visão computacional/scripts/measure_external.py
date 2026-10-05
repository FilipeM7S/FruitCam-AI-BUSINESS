import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from belt.classify import CropClassifier
from belt.detect import BeltDetector
from belt.stats import wilson

PROCESSED = ROOT / "data" / "processed"
DOCS = ROOT / "docs" / "datasets"
MODEL = Path(os.environ.get("FRUITCAM_MODEL_PATH", ROOT / "models" / "belt_v2.pt"))
SETS = ("potatoes", "lemons")
PRED = ("boa", "baixa_qualidade", "podre")
TRUE = ("good", "poor", "rotten", "poor_or_rotten")
CORRECT = {"good": {"boa"}, "poor": {"baixa_qualidade"}, "rotten": {"podre"}, "poor_or_rotten": {"baixa_qualidade", "podre"}}
GRAY = 128
NOTES = {
    "potatoes": "Reading: the mask is poor on this belt. It cuts holes into the potatoes and keeps parts of the grey-blue belt (see the examples), the same colour-segmentation failure measured on this dataset in CAMERA.md section 7. The grey-background numbers therefore mix background removal with damage to the fruit image and are not a clean background effect. As published, the model calls almost every potato not good.",
    "lemons": "Reading: the mask cuts each lemon out cleanly (see the examples), so this is a clean background swap. With the dataset's black background the answers are spread over the three classes; with a grey background the model calls almost every lemon boa, defective or not. For these crops, the model's output depends more on the background than on the fruit.",
}


def mask_of(rgb):
    bgr = np.ascontiguousarray(rgb[:, :, ::-1])
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    border = np.concatenate([lab[:4].reshape(-1, 3), lab[-4:].reshape(-1, 3), lab[:, :4].reshape(-1, 3), lab[:, -4:].reshape(-1, 3)])
    detector = BeltDetector(px_per_mm=1.0, min_area_mm2=0, max_area_mm2=10 ** 9, adapt=0)
    detector.belt = np.median(border, axis=0)
    _, mask = detector.detect(bgr)
    return mask


def predict(classifier, crops):
    out = []
    for i in range(0, len(crops), 128):
        p = classifier.probs([np.ascontiguousarray(c[:, :, ::-1]) for c in crops[i:i + 128]])
        out += [PRED[int(k)] for k in p.argmax(1)]
    return out


def scores(truth, pred):
    labels = [l for l in TRUE if l in truth]
    confusion = {t: {p: sum(1 for a, b in zip(truth, pred) if a == t and b == p) for p in PRED} for t in labels}
    per = {}
    for t in labels:
        n = sum(confusion[t].values())
        k = sum(confusion[t][p] for p in CORRECT[t])
        per[t] = {"n": n, "correct": k, "rate": k / n, "ci95": wilson(k, n)}
    good_true = [a == "good" for a in truth]
    good_pred = [b == "boa" for b in pred]
    hits = [x == y for x, y in zip(good_true, good_pred)]
    rec_good = sum(1 for x, y in zip(good_true, good_pred) if x and y) / max(sum(good_true), 1)
    rec_bad = sum(1 for x, y in zip(good_true, good_pred) if not x and not y) / max(len(good_true) - sum(good_true), 1)
    return {"n": len(truth), "confusion": confusion, "per_class": per, "binary_good_vs_not_good": {"accuracy": sum(hits) / len(hits), "balanced": (rec_good + rec_bad) / 2, "recall_good": rec_good, "recall_not_good": rec_bad}, "predicted": dict(Counter(pred))}


def sheet(examples, path):
    tile = 112
    img = Image.new("RGB", (len(examples) * (tile + 4) + 4, 2 * (tile + 4) + 4), (20, 35, 30))
    for i, (a, m) in enumerate(examples):
        img.paste(Image.fromarray(a).resize((tile, tile)), (4 + i * (tile + 4), 4))
        img.paste(Image.fromarray(m).resize((tile, tile)), (4 + i * (tile + 4), tile + 8))
    img.save(path)


def md_table(s):
    lines = ["| True label (n) | predicted boa | predicted baixa_qualidade | predicted podre | counted as correct | rate (95% CI) |", "|---|---|---|---|---|---|"]
    for t, row in s["confusion"].items():
        p = s["per_class"][t]
        lines.append(f"| {t} ({p['n']}) | {row['boa']} | {row['baixa_qualidade']} | {row['podre']} | {' or '.join(sorted(CORRECT[t]))} | {p['rate'] * 100:.1f}% ({p['ci95'][0] * 100:.1f}–{p['ci95'][1] * 100:.1f}%) |")
    b = s["binary_good_vs_not_good"]
    lines += ["", f"Good versus not good: accuracy {b['accuracy'] * 100:.1f}%, balanced {b['balanced'] * 100:.1f}% (recall good {b['recall_good'] * 100:.1f}%, recall not good {b['recall_not_good'] * 100:.1f}%), n = {s['n']}."]
    return lines


def main():
    classifier = CropClassifier(MODEL)
    result = {"model": {"file": MODEL.name, "version": classifier.version, "temperature": classifier.temperature, "reject_below": classifier.reject_below}, "masking": "background = pixels outside the pipeline's Lab-distance mask (BeltDetector: threshold 14, lightness weight 0.5, open 3x3, close 9x9), with the background colour taken as the median of a 4-pixel border of each crop; background pixels set to RGB (128, 128, 128)", "sets": {}}
    report = ["# A5: background sensitivity of the current model on potato and lemon crops", "", "**What this is.** The current cashew model (`" + MODEL.name + "`, unchanged) classifies every converted crop of two non-cashew datasets twice: as published, and with the background replaced by constant grey using the segmentation the camera pipeline already does. **These numbers measure how much the model's output depends on the background. They are not accuracy figures for cashew or for the product**: potatoes and lemons are different fruits, and the model was trained only on cashew field photos.", "", "In the product this model sends every fruit to manual review (no confidence level reached 95% accuracy on validation). Here the top class is used anyway, only to measure sensitivity.", "", "How a prediction is counted as correct: `good` → boa; `poor` → baixa_qualidade; `rotten` → podre; `poor_or_rotten` (the source does not separate minor defects from rot) → baixa_qualidade or podre.", ""]
    for name in SETS:
        rows = list(csv.DictReader((PROCESSED / name / "manifest.csv").open(encoding="utf-8")))
        crops = [np.asarray(Image.open(PROCESSED / name / r["file"]).convert("RGB")) for r in rows]
        masks = [mask_of(c) for c in crops]
        masked = []
        for c, m in zip(crops, masks):
            x = c.copy()
            x[m == 0] = GRAY
            masked.append(x)
        truth = [r["label"] for r in rows]
        plain_pred = predict(classifier, crops)
        masked_pred = predict(classifier, masked)
        fg = np.array([m.mean() for m in masks])
        centre = np.array([m[56:72, 56:72].mean() >= 0.9 for m in masks])
        changed = sum(1 for a, b in zip(plain_pred, masked_pred) if a != b)
        result["sets"][name] = {
            "n": len(rows),
            "as_published": scores(truth, plain_pred),
            "background_grey": scores(truth, masked_pred),
            "predictions_changed_by_masking": {"k": changed, "n": len(rows), "share": changed / len(rows)},
            "note": NOTES[name],
            "mask_quality": {"median_foreground_share": float(np.median(fg)), "share_with_centre_foreground": float(centre.mean()), "share_masking_nothing": float((fg > 0.99).mean()), "share_masking_almost_all": float((fg < 0.05).mean())},
        }
        idx = np.linspace(0, len(rows) - 1, 8).astype(int)
        sheet([(crops[i], masked[i]) for i in idx], DOCS / f"a5_mask_examples_{name}.png")
        s = result["sets"][name]
        q = s["mask_quality"]
        report += [f"## {name} (n = {s['n']})", "", f"Mask quality: median {q['median_foreground_share'] * 100:.0f}% of the crop kept as fruit; centre of the crop kept in {q['share_with_centre_foreground'] * 100:.0f}% of crops; mask kept almost everything in {q['share_masking_nothing'] * 100:.0f}% and almost nothing in {q['share_masking_almost_all'] * 100:.0f}%. Examples (top: as published, bottom: grey background): [a5_mask_examples_{name}.png](a5_mask_examples_{name}.png).", "", "### As published", "", *md_table(s["as_published"]), "", "### Background replaced by grey", "", *md_table(s["background_grey"]), "", f"Masking changed the predicted class for {s['predictions_changed_by_masking']['k']} of {s['n']} crops ({s['predictions_changed_by_masking']['share'] * 100:.1f}%).", "", NOTES[name], ""]
    (DOCS / "a5_measurement.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    (DOCS / "a5_background_sensitivity.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({k: {"n": v["n"], "changed": v["predictions_changed_by_masking"], "plain": {t: round(p["rate"], 3) for t, p in v["as_published"]["per_class"].items()}, "grey": {t: round(p["rate"], 3) for t, p in v["background_grey"]["per_class"].items()}, "mask": v["mask_quality"]} for k, v in result["sets"].items()}, indent=1))


if __name__ == "__main__":
    main()
