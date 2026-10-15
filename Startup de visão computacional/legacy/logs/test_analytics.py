import os
import tempfile
from datetime import datetime

import numpy as np
import pandas as pd
from PIL import Image
from scipy import stats

import analytics as A
import report
from records import COLUMNS, append_record
from records_synth import make_synthetic_records

MONDAY = pd.Timestamp("2025-01-06")


def labelled(weeks, sector="A", fruit="caju"):
    rows = []
    for w, counts in enumerate(weeks):
        k = 0
        for label, n in counts.items():
            for _ in range(n):
                rows.append((MONDAY + pd.Timedelta(weeks=w, minutes=k), sector, fruit, label))
                k += 1
    return pd.DataFrame(rows, columns=["timestamp", "sector", "fruit", "label"])


def good_bad(weekly, sector="A"):
    return labelled([{"nao_podre": g, "podre": b} for g, b in weekly], sector)


def expect_error(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def rates_frame(rates, n, sector, rng):
    stamps = np.repeat(MONDAY + pd.to_timedelta(np.arange(len(rates)) * 7, unit="D"), n)
    bad = rng.random(len(stamps)) < np.repeat(rates, n)
    return pd.DataFrame({
        "timestamp": stamps, "sector": sector, "fruit": "caju",
        "label": np.where(bad, "podre", "nao_podre"),
    })


def test_records_roundtrip_and_validation():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "r.csv")
        stamps = [datetime(2025, 1, 6, 8, 0, 0), datetime(2025, 1, 6, 8, 0, 5), datetime(2025, 1, 13, 9, 30, 0)]
        append_record(path, stamps[0], "norte", "caju", "nao_podre", 0.91234567, "L1")
        append_record(path, stamps[1], "sul, interior", "melao", "podre", 0.5)
        append_record(path, stamps[2], "norte", "caju", "podre", 0.75, "L2")
        with open(path) as f:
            lines = f.read().splitlines()
        assert len(lines) == 4 and lines[0] == ",".join(COLUMNS), lines
        df = A.load_records(path)
        assert list(df.columns) == COLUMNS
        assert df["timestamp"].tolist() == stamps
        assert df.loc[1, "sector"] == "sul, interior"
        assert abs(df.loc[0, "confidence"] - 0.912346) < 1e-9
        assert df["label"].tolist() == ["nao_podre", "podre", "podre"]

        no_label = os.path.join(d, "a.csv")
        pd.DataFrame({"timestamp": ["2025-01-06"], "sector": ["x"], "fruit": ["caju"]}).to_csv(no_label, index=False)
        expect_error(A.load_records, no_label)
        null_sector = os.path.join(d, "b.csv")
        pd.DataFrame({"timestamp": ["2025-01-06"], "sector": [None], "fruit": ["caju"], "label": ["podre"]}).to_csv(null_sector, index=False)
        expect_error(A.load_records, null_sector)
        header_only = os.path.join(d, "c.csv")
        pd.DataFrame(columns=COLUMNS).to_csv(header_only, index=False)
        expect_error(A.load_records, header_only)
    print("test_records_roundtrip_and_validation OK")


def test_weekly_defects_predominance():
    weeks = [
        {"nao_podre": 5, "podre": 3, "queimada": 1},
        {"podre": 1, "queimada": 4},
        {"nao_podre": 6},
        {"podre": 2, "queimada": 2},
    ]
    df = labelled(weeks)
    t = A.weekly_defects(df)
    assert list(t.columns) == ["podre", "queimada"]
    assert t.to_numpy().tolist() == [[3, 1], [1, 4], [0, 0], [2, 2]]
    assert t.index.tolist() == [MONDAY + pd.Timedelta(weeks=w) for w in range(4)]
    p = A.predominant_defect(t)
    assert p["top"].tolist() == ["podre", "queimada", "none", "podre"]
    assert np.allclose(p["share"].to_numpy(), [0.75, 0.8, np.nan, 0.5], equal_nan=True)
    assert p["n_defects"].tolist() == [4, 5, 0, 4]

    all_good = labelled([{"nao_podre": 4}, {"nao_podre": 2}])
    pg = A.predominant_defect(A.weekly_defects(all_good))
    assert pg["top"].tolist() == ["none", "none"] and pg["n_defects"].tolist() == [0, 0]
    assert pg["share"].isna().all()
    print("test_weekly_defects_predominance OK")


def test_period_counts_and_growth_exact():
    weekly = [(10, 4), (20, 2), (30, 0), (15, 3), (0, 3), (5, 6)]
    df = good_bad(weekly)
    full = A.period_counts(df, trim=False)
    assert full["good"].tolist() == [10, 20, 30, 15, 0, 5]
    assert full["bad"].tolist() == [4, 2, 0, 3, 3, 6]

    g = A.growth(df, trim=False)
    assert np.allclose(g["good_growth_pct"], [np.nan, 100, 50, -50, -100, np.nan], equal_nan=True)
    assert np.allclose(g["bad_growth_pct"], [np.nan, -50, -100, np.nan, 0, 100], equal_nan=True)

    kept = A.growth(df, trim=True)
    assert kept["good"].tolist() == [20, 30, 15, 0] and kept["bad"].tolist() == [2, 0, 3, 3]
    assert np.allclose(kept["good_growth_pct"], [np.nan, 50, -50, -100], equal_nan=True)
    assert np.allclose(kept["bad_growth_pct"], [np.nan, -100, np.nan, 0], equal_nan=True)

    gap = good_bad([(10, 1), (10, 1), (0, 0), (5, 1), (5, 1)])
    gg = A.growth(gap, trim=False)
    assert gg["good"].tolist() == [10, 10, 0, 5, 5] and gg["bad"].tolist() == [1, 1, 0, 1, 1]
    assert np.allclose(gg["good_growth_pct"], [np.nan, 0, -100, np.nan, 0], equal_nan=True)

    og = A.overall_growth(full)
    assert abs(og["good"] - (-50.0)) < 1e-12 and abs(og["bad"] - 50.0) < 1e-12
    zero_first = A.overall_growth(pd.DataFrame({"good": [0, 5], "bad": [2, 1]}))
    assert np.isnan(zero_first["good"]) and abs(zero_first["bad"] - (-50.0)) < 1e-12
    expect_error(A.overall_growth, full.iloc[:1])
    print("test_period_counts_and_growth_exact OK")


def test_monthly_growth_exact():
    def month_rows(month, good, bad):
        return [(pd.Timestamp(2025, month, 1 + k), "A", "caju", "nao_podre" if k < good else "podre") for k in range(good + bad)]

    rows = month_rows(1, 4, 1) + month_rows(2, 6, 2) + month_rows(3, 3, 4) + month_rows(4, 1, 1)
    df = pd.DataFrame(rows, columns=["timestamp", "sector", "fruit", "label"])
    g = A.growth(df, freq="M", trim=True)
    assert g["good"].tolist() == [6, 3] and g["bad"].tolist() == [2, 4]
    assert np.allclose(g["good_growth_pct"], [np.nan, -50], equal_nan=True)
    assert np.allclose(g["bad_growth_pct"], [np.nan, 100], equal_nan=True)
    print("test_monthly_growth_exact OK")


def test_fruit_volume_exact():
    rows = [("caju", "nao_podre")] * 4 + [("caju", "podre")] * 2 + [("castanha", "nao_podre")] * 3 + [("melao", "podre")]
    df = pd.DataFrame({
        "timestamp": [MONDAY + pd.Timedelta(minutes=i) for i in range(len(rows))],
        "sector": "A", "fruit": [r[0] for r in rows], "label": [r[1] for r in rows],
    })
    v = A.fruit_volume(df)
    assert v.index.tolist() == ["caju", "castanha", "melao"]
    assert v["n"].tolist() == [6, 3, 1] and v["good"].tolist() == [4, 3, 0]
    assert np.allclose(v["share"], [0.6, 0.3, 0.1])
    print("test_fruit_volume_exact OK")


def test_ols_forecast_against_independent_references():
    y = 3 + 2 * np.arange(10.0)
    mean, lo, hi, se, dof = A.ols_forecast(y, steps=1)
    assert abs(mean - 23.0) < 1e-9 and abs(hi - lo) < 1e-8 and dof == 8

    rng = np.random.default_rng(7)
    n, steps = 25, 3
    t = np.arange(n, dtype=float)
    y = 5 + 0.8 * t + rng.normal(0, 2.0, n)
    mean, lo, hi, se, dof = A.ols_forecast(y, steps=steps, level=0.90)
    lr = stats.linregress(t, y)
    t_new = n - 1 + steps
    assert abs(mean - (lr.intercept + lr.slope * t_new)) < 1e-9

    X = np.column_stack([np.ones(n), t])
    beta = np.linalg.solve(X.T @ X, X.T @ y)
    resid = y - X @ beta
    s2 = resid @ resid / (n - 2)
    x0 = np.array([1.0, t_new])
    se_ref = np.sqrt(s2 * (1 + x0 @ np.linalg.solve(X.T @ X, x0)))
    assert abs(se - se_ref) < 1e-10
    q = stats.t.ppf(0.95, n - 2)
    assert abs((hi - lo) / 2 - q * se_ref) < 1e-10 and dof == n - 2
    print("test_ols_forecast_against_independent_references OK")


def test_prediction_interval_coverage_monte_carlo():
    rng = np.random.default_rng(123)
    n, sims, hits = 20, 4000, 0
    t = np.arange(n + 1, dtype=float)
    for _ in range(sims):
        y = 20 + 0.5 * t + rng.normal(0, 3.0, n + 1)
        _, lo, hi, _, _ = A.ols_forecast(y[:n], steps=1, level=0.95)
        hits += lo <= y[n] <= hi
    coverage = hits / sims
    assert 0.938 <= coverage <= 0.962, coverage
    print("test_prediction_interval_coverage_monte_carlo OK", f"coverage={coverage:.4f}")


def test_p_positive_edge_cases():
    assert A.p_positive(2.0, 0.0, 5) == 1.0
    assert A.p_positive(-2.0, 0.0, 5) == 0.0
    assert A.p_positive(0.0, 0.0, 5) == 0.5
    assert abs(A.p_positive(0.0, 1.0, 7) - 0.5) < 1e-12
    assert abs(A.p_positive(1.3, 0.8, 9) + A.p_positive(-1.3, 0.8, 9) - 1.0) < 1e-12
    print("test_p_positive_edge_cases OK")


def test_forecast_exact_cases_and_symmetry():
    weeks = range(14)
    line = good_bad([(10 + 2 * w, 50 - w) for w in weeks], sector="A")
    const = good_bad([(12, 10)] * 14, sector="B")
    late = good_bad([(0, 0)] * 9 + [(7, 3), (7, 3), (7, 3)], sector="C")
    df = pd.concat([line, const, late]).sort_values("timestamp").reset_index(drop=True)

    f = A.forecast(df, min_weeks=8)
    assert f["target_week"].nunique() == 1 and f["target_week"].iloc[0] == MONDAY + pd.Timedelta(weeks=13)
    assert f.loc["A", "n_weeks"] == 12
    assert abs(f.loc["A", "good_pred"] - 36.0) < 1e-6 and abs(f.loc["A", "bad_pred"] - 37.0) < 1e-6
    assert abs(f.loc["A", "diff_pred"] - (-1.0)) < 1e-6 and f.loc["A", "p_good_gt_bad"] < 1e-9
    assert f.loc["B", "good_pred"] == 12.0 and f.loc["B", "bad_pred"] == 10.0 and f.loc["B", "p_good_gt_bad"] == 1.0
    assert f.loc["C", "n_weeks"] == 3 and np.isnan(f.loc["C", "good_pred"]) and np.isnan(f.loc["C", "p_good_gt_bad"])
    assert (f[["good_pred", "good_lo", "good_hi", "bad_pred", "bad_lo", "bad_hi"]].dropna() >= 0).all().all()

    swapped = A.forecast(df, good=("podre",), min_weeks=8)
    for sector in ("A", "B"):
        assert abs(f.loc[sector, "good_pred"] - swapped.loc[sector, "bad_pred"]) < 1e-9
        assert abs(f.loc[sector, "bad_pred"] - swapped.loc[sector, "good_pred"]) < 1e-9
        assert abs(f.loc[sector, "p_good_gt_bad"] + swapped.loc[sector, "p_good_gt_bad"] - 1.0) < 1e-9

    step2 = A.forecast(df, min_weeks=8, steps=2)
    assert abs(step2.loc["A", "good_pred"] - 38.0) < 1e-6
    assert step2["target_week"].iloc[0] == MONDAY + pd.Timedelta(weeks=14)
    expect_error(A.forecast, df, min_weeks=2)

    clipped = good_bad([(20 - 3 * w if 20 - 3 * w > 0 else 0, 5) for w in weeks], sector="D")
    assert A.forecast(clipped, min_weeks=8).loc["D", "good_pred"] >= 0
    print("test_forecast_exact_cases_and_symmetry OK")


def test_recurrence_exact():
    good = [9, 10, 12, 11, 13, 14, 15, 14, 16, 17, 18, 19, 18, 9]
    df = good_bad([(g, 5) for g in good])
    kept = good[1:13]
    gg = [100 * (b - a) / a for a, b in zip(kept[:-1], kept[1:])]
    jan, feb, mar = gg[0:2], gg[2:6], gg[6:11]

    m = A.recurrence(df, by="month")
    assert m.index.tolist() == [1, 2, 3]
    assert m["good_n"].tolist() == [2, 4, 5]
    assert np.allclose(m["good_frac_up"], [np.mean(np.array(x) > 0) for x in (jan, feb, mar)])
    assert np.allclose(m["good_median_growth_pct"], [np.median(x) for x in (jan, feb, mar)])
    assert m["bad_n"].tolist() == [2, 4, 5]
    assert np.allclose(m["bad_frac_up"], 0.0) and np.allclose(m["bad_median_growth_pct"], 0.0)

    s = A.recurrence(df, by="season")
    assert s.index.tolist() == ["verao", "outono"]
    verao = jan + feb
    assert s["good_n"].tolist() == [6, 5]
    assert np.allclose(s["good_frac_up"], [np.mean(np.array(verao) > 0), np.mean(np.array(mar) > 0)])

    w = A.recurrence(df, by="week")
    assert w.index.tolist() == list(range(3, 15))
    assert w.loc[3, "good_n"] == 0 and np.isnan(w.loc[3, "good_frac_up"])
    assert w.loc[4, "good_frac_up"] == 1.0 and w.loc[5, "good_frac_up"] == 0.0
    assert w["good_n"].sum() == 11

    custom = {1: "seca", 2: "chuvosa", 3: "chuvosa"}
    c = A.recurrence(df, by="season", seasons=custom)
    assert c.index.tolist() == ["seca", "chuvosa"]
    assert c["good_n"].tolist() == [2, 9]
    print("test_recurrence_exact OK")


def test_sector_gaussian_exact():
    a = good_bad([(90, 10), (80, 20), (70, 30), (60, 40), (50, 50)], sector="A")
    b = good_bad([(9, 1), (8, 2), (80, 20), (70, 30), (90, 10)], sector="B")
    df = pd.concat([a, b]).sort_values("timestamp").reset_index(drop=True)
    rates = A.sector_rates(df, min_fruits=30)
    assert len(rates.xs("A", level=0)) == 5 and len(rates.xs("B", level=0)) == 3
    fit = A.gaussian_fit(rates)
    assert abs(fit.loc["A", "mean"] - 0.3) < 1e-12 and abs(fit.loc["A", "std"] - np.sqrt(0.025)) < 1e-12
    assert abs(fit.loc["B", "mean"] - 0.2) < 1e-12 and abs(fit.loc["B", "std"] - 0.1) < 1e-12
    assert fit["n_weeks"].tolist() == [5, 3]
    ra = rates.xs("A", level=0).to_numpy()
    assert abs(fit.loc["A", "shapiro_p"] - stats.shapiro(ra).pvalue) < 1e-12
    assert abs(fit.loc["A", "trend_per_week"] - 0.1) < 1e-12
    weeks_b = rates.xs("B", level=0).index.asi8
    assert abs(fit.loc["B", "trend_per_week"] - stats.linregress(weeks_b, rates.xs("B", level=0).to_numpy()).slope) < 1e-12
    print("test_sector_gaussian_exact OK")


def test_sector_gaussian_recovery_and_discrimination():
    rng = np.random.default_rng(11)
    mu, sigma, n, weeks = 0.30, 0.05, 500, 300
    gauss = np.clip(rng.normal(mu, sigma, weeks), 0, 1)
    half = weeks // 2
    bimodal = np.clip(np.concatenate([rng.normal(0.10, 0.01, half), rng.normal(0.50, 0.01, weeks - half)]), 0, 1)
    rng.shuffle(bimodal)
    df = pd.concat([rates_frame(gauss, n, "gauss", rng), rates_frame(bimodal, n, "bimodal", rng)])
    fit = A.gaussian_fit(A.sector_rates(df, min_fruits=30))
    expected_sd = np.sqrt(sigma ** 2 + mu * (1 - mu) / n)
    assert abs(fit.loc["gauss", "mean"] - mu) < 0.012, fit.loc["gauss"]
    assert abs(fit.loc["gauss", "std"] - expected_sd) < 0.008, fit.loc["gauss"]
    assert fit.loc["gauss", "shapiro_p"] > 0.01, fit.loc["gauss"]
    assert fit.loc["gauss", "trend_p"] > 0.01, fit.loc["gauss"]
    assert fit.loc["bimodal", "shapiro_p"] < 1e-3, fit.loc["bimodal"]
    print("test_sector_gaussian_recovery_and_discrimination OK", f"gauss_p={fit.loc['gauss', 'shapiro_p']:.3f} bimodal_p={fit.loc['bimodal', 'shapiro_p']:.2e}")


def test_end_to_end_planted_signals():
    with tempfile.TemporaryDirectory() as d:
        csv_path = os.path.join(d, "records.csv")
        out = os.path.join(d, "out")
        make_synthetic_records(csv_path, n_weeks=52, seed=0)
        res = report.run(csv_path, out)

        df = A.load_records(csv_path)
        pdm = A.predominant_defect(A.weekly_defects(df))
        assert len(pdm) == 52
        assert (pdm["top"].iloc[:26] == "podre").all() and (pdm["top"].iloc[26:] == "queimada").all()

        v = res["fruit_volume"]
        assert v.index[0] == "caju" and abs(v.loc["caju", "share"] - 0.6) < 0.01
        assert abs(v.loc["castanha", "share"] - 0.3) < 0.01

        f = res["forecast"]
        assert f.loc["norte", "p_good_gt_bad"] > 0.99 and f.loc["sul", "p_good_gt_bad"] > 0.99
        assert f.loc["serra", "p_good_gt_bad"] < 0.2 and f.loc["serra", "bad_pred"] > f.loc["serra", "good_pred"]

        g = res["gaussian"]
        assert abs(g.loc["norte", "mean"] - 0.05) < 0.01 and abs(g.loc["sul", "mean"] - 0.10) < 0.01
        assert g["std"].idxmax() == "serra" and g.loc["serra", "trend_p"] < 1e-6
        assert abs(g.loc["serra", "trend_per_week"] - (0.60 - 0.15) / 51) < 0.002
        assert g.loc["norte", "trend_p"] > 0.01 and g.loc["sul", "trend_p"] > 0.01

        for name in ("weekly_defects", "fruit_volume", "growth_weekly", "growth_monthly", "forecast",
                     "recurrence_week", "recurrence_month", "recurrence_season", "gaussian"):
            assert os.path.getsize(os.path.join(out, f"{name}.csv")) > 0, name
        for name in ("weekly_defects", "fruit_volume", "growth", "recurrence", "forecast", "gaussian"):
            with Image.open(os.path.join(out, f"{name}.png")) as im:
                im.load()
                assert im.size[0] > 400 and im.size[1] > 200, (name, im.size)
    print("test_end_to_end_planted_signals OK")


def run():
    test_records_roundtrip_and_validation()
    test_weekly_defects_predominance()
    test_period_counts_and_growth_exact()
    test_monthly_growth_exact()
    test_fruit_volume_exact()
    test_ols_forecast_against_independent_references()
    test_prediction_interval_coverage_monte_carlo()
    test_p_positive_edge_cases()
    test_forecast_exact_cases_and_symmetry()
    test_recurrence_exact()
    test_sector_gaussian_exact()
    test_sector_gaussian_recovery_and_discrimination()
    test_end_to_end_planted_signals()
    print("ALL ANALYTICS CHECKS PASSED")


if __name__ == "__main__":
    run()