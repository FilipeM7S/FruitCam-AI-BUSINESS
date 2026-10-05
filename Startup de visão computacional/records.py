import csv
import os

COLUMNS = ["timestamp", "sector", "fruit", "label", "confidence", "lot"]


def append_record(path, timestamp, sector, fruit, label, confidence, lot=""):
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(COLUMNS)
        writer.writerow([timestamp.isoformat(timespec="seconds"), sector, fruit, label, f"{confidence:.6f}", lot])