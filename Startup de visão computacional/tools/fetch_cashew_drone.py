import argparse
import datetime
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import remote_zip

STORE = Path(os.environ.get("FRUITCAM_DATA_STORE") or Path.home() / "FruitCamData")
HOME = STORE / "cashew_drone_full"
STAGES = {1: "premature", 2: "unripe", 3: "ripe", 4: "spoilt"}
MIN_SIDE = 0.022
TARGET = {"ripe": 4500, "unripe": 3200, "premature": 3200}
PICTURES = (".jpg", ".jpeg", ".png")


def dataset():
    meta = json.loads((ROOT / "scripts" / "datasets.json").read_text(encoding="utf-8"))
    return next(d for d in meta["datasets"] if d["id"] == "cashew_drone_full")


def entries_of(spec):
    path = HOME / f"index_{Path(spec['name']).stem}.json"
    if not path.exists():
        entries, _ = remote_zip.index(spec["url"], spec["size"])
        remote_zip.save_index(path, entries, {"url": spec["url"], "size": spec["size"], "sha256": spec.get("sha256")})
    return remote_zip.load_index(path)


def choose(labels, pictures):
    per_photo = {}
    for label_file in sorted(labels.glob("*.txt")):
        if label_file.stem not in pictures:
            continue
        count = Counter()
        for line in label_file.read_text(encoding="utf-8", errors="replace").splitlines():
            r = line.split()
            if len(r) >= 5 and int(float(r[0])) in STAGES and min(float(r[3]), float(r[4])) >= MIN_SIDE:
                count[STAGES[int(float(r[0]))]] += 1
        per_photo[label_file.stem] = count
    chosen, have = [], Counter()
    pool = dict(per_photo)
    for stem in sorted(pool):
        if pool[stem]["spoilt"]:
            chosen.append(stem)
            have.update(pool.pop(stem))
    while pool:
        need = {k: TARGET[k] - have[k] for k in TARGET if have[k] < TARGET[k]}
        if not need:
            break
        scarce = max(sorted(need), key=lambda k: need[k] / TARGET[k])
        best = max(sorted(pool), key=lambda s: (pool[s][scarce], sum(pool[s].values())))
        if pool[best][scarce] == 0:
            break
        chosen.append(best)
        have.update(pool.pop(best))
    return chosen, dict(have)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels-only", action="store_true")
    args = parser.parse_args()
    ds = dataset()
    report = {"fetched_on": datetime.date.today().isoformat(), "method": "HTTP range requests on the pinned archive URLs; every file checked against the size and CRC-32 recorded in the archive's own index; the archives were not downloaded in full, so their published SHA-256 was not checked", "archives": {}}
    for spec in ds["files"]:
        if not spec["name"].endswith(".zip"):
            continue
        stem = Path(spec["name"]).stem
        entries = entries_of(spec)
        folder = HOME / "members" / stem
        labels = [e for e in entries if e["name"].lower().endswith(".txt")]
        got = remote_zip.mirror(spec["url"], spec["size"], labels, folder)
        photos = {Path(e["name"]).stem: e for e in entries if e["name"].lower().endswith(PICTURES)}
        info = {"url": spec["url"], "size": spec["size"], "sha256_published": spec.get("sha256"), "files_in_archive": len(entries), "photos_in_archive": len(photos), "label_files": len(labels), "label_files_fetched_now": got["files"]}
        if stem == "ghana_cashew" and not args.labels_only:
            chosen, boxes = choose(folder / "Labels", photos)
            done = remote_zip.mirror(spec["url"], spec["size"], [photos[s] for s in chosen], folder, progress=50)
            (HOME / "selection_ghana.json").write_text(json.dumps(chosen), encoding="utf-8")
            info.update(photos_selected=len(chosen), photos_fetched_now=done["files"], fruit_boxes_in_selection=boxes, selection_rule=f"every photo with a spoilt fruit, then the photos richest in the scarcest stage until {TARGET} boxes with a shorter side of at least {MIN_SIDE} of the photo")
        present = [e for e in entries if remote_zip.present(folder / e["name"], e)]
        info.update(files_present_and_matching_crc=len(present), photos_present=sum(e["name"].lower().endswith(PICTURES) for e in present), bytes_present=sum(e["size"] for e in present))
        report["archives"][spec["name"]] = info
        print(f"{spec['name']}: {info['files_present_and_matching_crc']} files present and matching the archive index ({info['photos_present']} photos, {info['bytes_present'] / 1e6:.0f} MB)")
    (HOME / "intake.json").write_text(json.dumps(report, indent=1) + chr(10), encoding="utf-8")


if __name__ == "__main__":
    main()
