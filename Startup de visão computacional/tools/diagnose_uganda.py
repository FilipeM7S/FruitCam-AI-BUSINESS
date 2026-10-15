import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import remote_zip
from training import cashew_data as D

OUT = ROOT / "docs" / "reports" / "uganda_diagnosis"
HOME = D.STORE / "cashew_drone_full"
ORIGINALS = HOME / "members" / "uganda_cashew"
PAPER = ["tree", "flower", "premature", "unripe", "ripe", "spoilt"]
ALPHA = ["flower", "premature", "unripe", "ripe", "spoilt", "tree"]
NAMES = {"uganda_a": PAPER, "uganda_b": ALPHA, "ghana": ALPHA}
TITLES = {"ghana": "Gana", "uganda_b": "Uganda, segundo lote", "uganda_a": "Uganda, primeiro lote (excluído)"}
PUBLISHED = {"tree": 5347, "flower": 23169, "premature": 21200, "unripe": 5347, "ripe": 7481, "spoilt": 25820}
TILE = 96


def label_files():
    out = {"ghana": sorted(D.SOURCES["ghana"]["labels"].glob("*.txt")), "uganda_a": [], "uganda_b": [], "uganda_unknown": []}
    for path in sorted(D.SOURCES["uganda"]["labels"].glob("*.txt")):
        out[{"paper": "uganda_a", "alpha": "uganda_b", None: "uganda_unknown"}[D.label_order(D.rows_of(path))]].append(path)
    return out


def number(stem):
    digits = "".join(ch for ch in stem if ch.isdigit())
    return int(digits) if digits else None


def label_table(files):
    table, by_id = {}, Counter()
    for source, paths in files.items():
        boxes = {}
        for path in paths:
            for c, _, _, w, h in D.rows_of(path):
                boxes.setdefault(c, []).append((w, h))
                if source != "ghana":
                    by_id[c] += 1
        names = NAMES.get(source)
        numbers = [n for n in (number(p.stem) for p in paths) if n is not None]
        table[source] = {
            "files": len(paths),
            "file_number_p10_p50_p90": [int(v) for v in np.percentile(numbers, [10, 50, 90])] if numbers else None,
            "classes": {str(c): {"name_in_this_order": names[c] if names else None, "boxes": len(v), "per_file": len(v) / max(len(paths), 1), "median_width": float(np.median([w for w, _ in v])), "median_height": float(np.median([h for _, h in v]))} for c, v in sorted(boxes.items())},
        }
    paper = {name: {"published": PUBLISHED[name], "boxes_with_this_id_in_all_uganda_files": by_id[i]} for i, name in enumerate(PAPER)}
    return table, paper


def photo_stats(source, files, sample, seed):
    rng = np.random.default_rng(seed)
    picked = [files[i] for i in rng.choice(len(files), min(sample, len(files)), replace=False)]
    folder = D.SOURCES["ghana" if source == "ghana" else "uganda"]["images"]
    sizes, light, colour, sharp, hues = Counter(), [], [], [], np.zeros(12)
    for path in picked:
        image = D.picture(folder, path.stem)
        if image is None:
            continue
        with Image.open(image) as im:
            sizes[im.size] += 1
            rgb = np.asarray(im.convert("RGB").resize((320, 240), Image.BILINEAR))
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        light.append(lab[..., 0].mean() * 100 / 255)
        colour.append(hsv[..., 1].mean() / 255)
        sharp.append(cv2.Laplacian(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var())
        strong = hsv[..., 1] > 60
        hues += np.bincount((hsv[..., 0][strong].astype(int) * 12 // 180).clip(0, 11), minlength=12)
    return {"photos_measured": len(light), "sizes": {f"{w}x{h}": n for (w, h), n in sizes.most_common(3)}, "lightness_mean": float(np.mean(light)), "lightness_sd": float(np.std(light)), "saturation_mean": float(np.mean(colour)), "sharpness_median": float(np.median(sharp)), "hue_histogram_of_saturated_pixels": (hues / max(hues.sum(), 1)).round(4).tolist()}


def crop_features(row, files):
    rgb = np.asarray(files.image(row))
    mask = files.mask(row).astype(bool)
    if mask.sum() < 20:
        mask[:] = True
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(float)
    hue, sat, val = hsv[..., 0][mask].astype(int), hsv[..., 1][mask], hsv[..., 2][mask]
    vivid = sat > 60
    warm = vivid & ((hue < 20) | (hue > 165))
    yellow = vivid & (hue >= 20) & (hue < 35)
    green = vivid & (hue >= 35) & (hue < 90)
    return [lab[..., 0][mask].mean() * 100 / 255, lab[..., 1][mask].mean() - 128, lab[..., 2][mask].mean() - 128, sat.mean() / 255, warm.mean(), yellow.mean(), green.mean(), (val < 70).mean()]


FEATURES = ["lightness", "red_minus_green", "yellow_minus_blue", "saturation", "share_red", "share_yellow", "share_green", "share_dark"]


def crop_table(rows, files, cap, seed):
    out, feats = {}, {}
    for source in ("ghana", "uganda_b", "uganda_a"):
        for stage in D.STAGES:
            mine = sorted((r for r in rows if r["source"] == source and r["stage"] == stage), key=lambda r: D.rank(f"{seed}:{r['key']}"))
            used = mine[:cap]
            f = np.array([crop_features(r, files) for r in used]) if used else np.zeros((0, len(FEATURES)))
            feats[(source, stage)] = (used, f)
            side = np.array([min(float(r["box_w"]), float(r["box_h"])) for r in mine]) if mine else np.zeros(0)
            out[f"{source}/{stage}"] = {"crops": len(mine), "photos": len({r["photo"] for r in mine}), "measured": len(used), "median_short_side_px": float(np.median(side)) if len(side) else None, **({name: float(v) for name, v in zip(FEATURES, f.mean(axis=0))} if len(f) else {})}
    return out, feats


def colour_probe(feats, seed):
    def fit(parts):
        x = np.concatenate([f for _, f in parts])
        mean, sd = x.mean(axis=0), x.std(axis=0) + 1e-9
        return mean, sd

    trusted = {stage: [feats[(s, stage)] for s in ("ghana", "uganda_b")] for stage in D.STAGES}
    train, test = {}, {}
    for stage, parts in trusted.items():
        rows = [r for used, _ in parts for r in used]
        f = np.concatenate([f for _, f in parts])
        held = np.array([r["split"] == "test" for r in rows])
        train[stage], test[stage] = f[~held], f[held]
    mean, sd = fit([(None, np.concatenate(list(train.values())))])
    centres = np.stack([((train[s] - mean) / sd).mean(axis=0) for s in D.STAGES])

    def answer(f):
        z = (f - mean) / sd
        return np.linalg.norm(z[:, None, :] - centres[None], axis=2).argmin(axis=1)

    check = {s: {"n": int(len(test[s])), "answers": {t: int((answer(test[s]) == i).sum()) for i, t in enumerate(D.STAGES)}} for s in D.STAGES if len(test[s])}
    recall = [check[s]["answers"][s] / check[s]["n"] for s in check]
    probe = {}
    for stage in D.STAGES:
        _, f = feats[("uganda_a", stage)]
        if len(f):
            probe[stage] = {"n": int(len(f)), "answers": {t: int((answer(f) == i).sum()) for i, t in enumerate(D.STAGES)}}
    return {"what": "nearest class centre on eight colour measures taken inside the fruit mask; centres fitted on training-split crops of Ghana and the second Uganda batch", "features": FEATURES, "check_on_held_out_trusted_crops": check, "balanced_accuracy_on_held_out_trusted_crops": float(np.mean(recall)), "first_batch_by_its_label": probe}


def tile(image):
    return np.asarray(Image.fromarray(image).resize((TILE, TILE), Image.LANCZOS))


def sheet(blocks, path, columns=6):
    gap, head = 14, 26
    width = sum(columns * TILE for _ in blocks) + gap * (len(blocks) - 1)
    rows = max(-(-len(tiles) // columns) for _, tiles in blocks)
    canvas = Image.new("RGB", (width, head + rows * TILE), (24, 36, 30))
    pen = ImageDraw.Draw(canvas)
    x = 0
    for title, tiles in blocks:
        pen.text((x + 4, 6), title, fill=(228, 238, 232))
        for i, t in enumerate(tiles):
            canvas.paste(Image.fromarray(t), (x + (i % columns) * TILE, head + (i // columns) * TILE))
        x += columns * TILE + gap
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, quality=88)
    return path.name


def crop_sheets(rows, files, out, each, seed):
    made = {}
    for stage in D.STAGES:
        blocks = []
        for source in ("ghana", "uganda_b", "uganda_a"):
            mine = sorted((r for r in rows if r["source"] == source and r["stage"] == stage), key=lambda r: D.rank(f"sheet:{seed}:{r['key']}"))[:each]
            blocks.append((f"{TITLES[source]} · {stage} · {len(mine)} recortes", [tile(np.asarray(files.image(r))) for r in mine]))
        made[stage] = sheet(blocks, out / f"recortes_{stage}.jpg")
    return made


def fetch_originals(files, each, seed):
    index = json.loads((HOME / "index_uganda_cashew.json").read_text(encoding="utf-8"))
    entries = {Path(e["name"]).stem: e for e in index["entries"] if e["name"].lower().endswith(".jpg")}
    wanted = {}
    for source in ("uganda_a", "uganda_b"):
        tree = D.TREE["paper" if source == "uganda_a" else "alpha"]
        variety = {p: len({c for c, *_ in D.rows_of(p)} - {tree}) for p in files[source] if p.stem in entries}
        wanted[source] = sorted(variety, key=lambda p: (-variety[p], D.rank(f"orig:{seed}:{p.stem}")))[:each]
    picked = [entries[p.stem] for paths in wanted.values() for p in paths]
    done = remote_zip.mirror(index["source"]["url"], index["source"]["size"], picked, ORIGINALS)
    return wanted, {"photos": len(picked), "bytes": sum(e["size"] for e in picked), "fetched_now": done["files"], "check": "size and CRC-32 of every photo against the archive index"}


def original_sheets(wanted, out, each, seed):
    made, sizes = {}, {}
    rng = np.random.default_rng(seed)
    for source, paths in wanted.items():
        boxes = {}
        for path in paths:
            image = next(ORIGINALS.rglob(f"{path.stem}.jpg"), None)
            if image is None:
                continue
            with Image.open(image) as im:
                rgb = np.asarray(im.convert("RGB"))
            h, w = rgb.shape[:2]
            for c, cx, cy, bw, bh in D.rows_of(path):
                if max(bw, bh) >= D.PHOTO_SIZED:
                    continue
                side = max(bw * w, bh * h) * 1.3
                x0, y0 = int(max(cx * w - side / 2, 0)), int(max(cy * h - side / 2, 0))
                cut = rgb[y0:int(min(y0 + side, h)), x0:int(min(x0 + side, w))]
                if min(cut.shape[:2]) >= 12:
                    boxes.setdefault(c, []).append((cut, max(bw * w, bh * h)))
        blocks = []
        for c in sorted(boxes):
            order = rng.permutation(len(boxes[c]))[:each]
            sizes[f"{source}/{c}"] = {"name_in_this_order": NAMES[source][c], "boxes_in_the_fetched_photos": len(boxes[c]), "median_long_side_px_at_full_resolution": float(np.median([s for _, s in boxes[c]]))}
            blocks.append((f"id {c} = {NAMES[source][c]} · {len(order)} de {len(boxes[c])}", [tile(boxes[c][i][0]) for i in order]))
        made[source] = sheet(blocks, out / f"originais_{source}.jpg", columns=5)
    return made, sizes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--photos", type=int, default=300)
    parser.add_argument("--crops", type=int, default=400)
    parser.add_argument("--each", type=int, default=30)
    parser.add_argument("--originals", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    out = Path(args.out)
    files = label_files()
    labels, paper = label_table(files)
    rows = D.manifest()
    crops = D.CropFiles([], None)
    table, feats = crop_table(rows, crops, args.crops, args.seed)
    wanted, fetched = fetch_originals(files, args.originals, args.seed)
    original, original_sizes = original_sheets(wanted, out, args.each, args.seed)
    result = {
        "what": "comparison of the excluded first Uganda label batch with the two trusted sources; diagnosis only, nothing was retrained",
        "labels": labels,
        "published_table_against_ids": paper,
        "photos": {source: photo_stats(source, files[source], args.photos, args.seed) for source in ("ghana", "uganda_b", "uganda_a")},
        "crops_of_at_least_24_px": table,
        "colour_probe": colour_probe(feats, args.seed),
        "model_probe": json.loads((ROOT / "models" / "first_batch_v3.json").read_text(encoding="utf-8")),
        "original_photos": {**fetched, "files": {s: [p.stem for p in paths] for s, paths in wanted.items()}, "boxes": original_sizes},
        "sheets": {"crops_by_stage": crop_sheets(rows, crops, out, args.each, args.seed), "full_resolution_by_class_id": original},
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"labels": {s: {c: (v["name_in_this_order"], v["boxes"], round(v["per_file"], 1)) for c, v in t["classes"].items()} for s, t in labels.items()}, "published": paper, "colour_probe": result["colour_probe"], "originals": fetched}, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
