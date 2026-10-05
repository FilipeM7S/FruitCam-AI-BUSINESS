import numpy as np
import pandas as pd

from records import COLUMNS

SECTORS = {"norte": (300, 0.05, 0.05), "sul": (200, 0.10, 0.10), "serra": (100, 0.15, 0.60)}
FRUITS = {"caju": 0.6, "castanha": 0.3, "melao": 0.1}
DEFECTS = ("podre", "queimada", "quebrada")


def make_synthetic_records(path, n_weeks=52, start="2025-01-06", seed=0):
    rng = np.random.default_rng(seed)
    monday = pd.Timestamp(start)
    frames = []
    for w in range(n_weeks):
        mix = (0.7, 0.2, 0.1) if w < n_weeks / 2 else (0.15, 0.7, 0.15)
        for sector, (volume, bad0, bad1) in SECTORS.items():
            n = rng.poisson(volume)
            bad = rng.random(n) < bad0 + (bad1 - bad0) * w / max(n_weeks - 1, 1)
            label = np.where(bad, rng.choice(DEFECTS, size=n, p=mix), "nao_podre")
            stamps = monday + pd.Timedelta(weeks=w) + pd.to_timedelta(rng.random(n) * 5, unit="D")
            frames.append(pd.DataFrame({
                "timestamp": stamps.floor("s"),
                "sector": sector,
                "fruit": rng.choice(list(FRUITS), size=n, p=list(FRUITS.values())),
                "label": label,
                "confidence": rng.uniform(0.5, 1.0, n).round(6),
                "lot": f"{sector}-{w:03d}",
            }))
    df = pd.concat(frames).sort_values("timestamp")
    df[COLUMNS].to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%S")
    return path


if __name__ == "__main__":
    make_synthetic_records("records_synthetic.csv")