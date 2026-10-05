import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from train_belt import tree_as_five

PAPER = ["tree", "flower", "premature", "unripe", "ripe", "spoilt"]
OUT = ROOT / "docs" / "datasets" / "cashew_label_audit"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    flagged = tree_as_five(ROOT / "Labels")
    rows, sides = [], {g: {c: [] for c in range(6)} for g in ("tree_as_5", "paper_order")}
    total = np.zeros(6, int)
    for f in sorted((ROOT / "Labels").glob("*.txt")):
        boxes = [r.split() for r in f.read_text().splitlines() if r.strip()]
        group = "tree_as_5" if f.stem in flagged else "paper_order"
        counts = np.zeros(6, int)
        for b in boxes:
            c = int(b[0])
            counts[c] += 1
            sides[group][c].append(max(float(b[3]), float(b[4])))
        total += counts
        rows.append({"file": f.name, "image": f"{f.stem}.jpg", "group": group, **{f"id{c}": int(counts[c]) for c in range(6)}, "id5_boxes_covering_60pct": sum(1 for b in boxes if int(b[0]) == 5 and max(float(b[3]), float(b[4])) >= 0.6)})
    with (OUT / "files.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "dataset": "Coffee and Cashew Nut Dataset, cashew part (doi:10.17632/r46c6bpfpf.1, CC BY 4.0)",
        "files": len(rows),
        "boxes_per_id": {f"{c} ({PAPER[c]})": int(total[c]) for c in range(6)},
        "rule": "a file is 'tree_as_5' when it has a class-5 box whose longer side covers at least 60% of the photo",
        "groups": {},
    }
    for g, d in sides.items():
        summary["groups"][g] = {"files": sum(r["group"] == g for r in rows), "per_id": {str(c): {"boxes": len(v), "median_longer_side_fraction": round(float(np.median(v)), 3) if v else None, "share_covering_60pct": round(float(np.mean(np.array(v) >= 0.6)), 3) if v else None} for c, v in d.items()}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
