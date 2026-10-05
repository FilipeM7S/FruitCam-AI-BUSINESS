import os
import sys
import tempfile

import numpy as np
import pandas as pd
from PIL import Image

import fruit_analytics as FA
from records import append_record

RESULTS = []
BASE = pd.Timestamp("2024-01-01")
DEMO_DIR = "analytics_demo_synthetic"


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def expand(spec, rng):
    s = pd.DataFrame(spec, columns=["start", "days", "sector", "fruit", "label", "n"])
    s = s[s["n"] > 0]
    rep = s.loc[s.index.repeat(s["n"])]
    offs = np.floor(rng.random(len(rep)) * rep["days"].to_numpy() * 86400)
    ts = pd.to_datetime(rep["start"].to_numpy()) + pd.to_timedelta(offs, unit="s")
    return pd.DataFrame({"timestamp": ts, "sector": rep["sector"].to_numpy(), "fruit": rep["fruit"].to_numpy(), "label": rep["label"].to_numpy()})


def week(w):
    return BASE + pd.Timedelta(weeks=w)


def month(m):
    start = BASE + pd.DateOffset(months=m)
    return start, start.days_in_month


def test_records_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "log.csv")
        for label in ("nao_podre", "podre", "queimada"):
            append_record(path, pd.Timestamp("2024-03-04 10:00:00").to_pydatetime(), "norte", "caju", label, 0.9, "L1")
        e = FA.load_events(path)
    check("records.py CSV -> event table columns", list(e.columns) == ["timestamp", "sector", "fruit_type", "is_good", "deformity_type"], list(e.columns))
    check("is_good derived from label", e["is_good"].tolist() == [True, False, False], e["is_good"].tolist())
    check("deformity_type = label for rotten, NaN for good",
          pd.isna(e["deformity_type"].iloc[0]) and e["deformity_type"].iloc[1:].tolist() == ["podre", "queimada"], e["deformity_type"].tolist())
    try:
        FA.to_events(pd.DataFrame(columns=["timestamp", "sector", "fruit", "label"]))
        check("empty event table raises", False)
    except ValueError as exc:
        check("empty event table raises", True, str(exc))


def test_dominant_deformity(seed=0):
    rng = np.random.default_rng(seed)
    kinds = ["podre", "queimada", "quebrada"]
    truth = {}
    spec = []
    for w in range(20):
        if w == 12:
            truth[w] = "none"
            continue
        if w == 15:
            n = [100, 100, 100]
            truth[w] = "tie"
        else:
            top = "queimada" if w < 7 else "podre" if w < 14 else "quebrada"
            truth[w] = top
            n = rng.multinomial(300, [0.6 if k == top else 0.2 for k in kinds])
        spec += [(week(w), 7, "A", "caju", k, c) for k, c in zip(kinds, n)]
        spec.append((week(w), 7, "A", "caju", "nao_podre", 700))
    e = FA.to_events(expand(spec, rng))
    dom = FA.dominant_deformity(FA.deformity_counts(e))
    weeks = [w for w in truth if truth[w] not in ("none", "tie")]
    got = [dom["dominant"].iloc[w] for w in weeks]
    check("weekly dominant deformity recovered (18 weeks)", got == [truth[w] for w in weeks], f"{sum(g == truth[w] for g, w in zip(got, weeks))}/{len(weeks)} correct")
    err = max(abs(dom["share"].iloc[w] - 0.6) for w in weeks)
    check("dominant share within 0.10 of true 0.60", err < 0.10, f"max |share-0.60| = {err:.4f}")
    check("empty week -> 'none', n_rotten=0, share NaN",
          dom["dominant"].iloc[12] == "none" and dom["n_rotten"].iloc[12] == 0 and np.isnan(dom["share"].iloc[12]), dom.iloc[12].to_dict())
    check("exact 3-way tie flagged", bool(dom["tie"].iloc[15]) and not dom["tie"].iloc[weeks].any(), dom.iloc[15].to_dict())
    check("no rotten fruit at all -> all 'none'", (FA.dominant_deformity(FA.deformity_counts(e[e["is_good"]]))["dominant"] == "none").all())


def test_growth_known_rate(seed=0):
    rng = np.random.default_rng(seed)
    spec = []
    for m in range(12):
        start, days = month(m)
        spec.append((start, days, "A", "caju", "nao_podre", round(10000 * 1.10 ** m)))
        spec.append((start, days, "A", "caju", "podre", round(1000 * 1.20 ** m)))
    g = FA.growth(FA.to_events(expand(spec, rng)), "month")
    m = np.arange(12)
    true_rp = 1000 * 1.2 ** m / (10000 * 1.1 ** m + 1000 * 1.2 ** m)
    true_gp = 1 - true_rp
    e_good = np.abs(g["good_count_growth"].iloc[1:] - 0.10).max()
    e_rot = np.abs(g["rotten_count_growth"].iloc[1:] - 0.20).max()
    e_rp = np.abs(g["rotten_prop_growth"].iloc[1:].to_numpy() - (true_rp[1:] / true_rp[:-1] - 1)).max()
    e_gp = np.abs(g["good_prop_growth"].iloc[1:].to_numpy() - (true_gp[1:] / true_gp[:-1] - 1)).max()
    check("good count growth = +10%/month (tol 0.001)", e_good < 0.001, f"max err {e_good:.2e}")
    check("rotten count growth = +20%/month (tol 0.001)", e_rot < 0.001, f"max err {e_rot:.2e}")
    check("rotten proportion growth matches analytic value (tol 0.001)", e_rp < 0.001, f"max err {e_rp:.2e}, e.g. month1 {g['rotten_prop_growth'].iloc[1]:.4f}")
    check("good proportion growth matches analytic value (tol 0.001)", e_gp < 0.001, f"max err {e_gp:.2e}, e.g. month1 {g['good_prop_growth'].iloc[1]:.4f}")
    first = g.iloc[0][["good_count_growth", "rotten_count_growth", "good_prop_growth", "rotten_prop_growth"]]
    check("first period growth is NaN (no previous)", first.isna().all())


def test_previous_zero_and_empty_period(seed=0):
    rng = np.random.default_rng(seed)
    spec = []
    for m, good, rot in [(0, 100, 0), (1, 0, 0), (2, 50, 20), (3, 60, 30)]:
        start, days = month(m)
        spec += [(start, days, "A", "caju", "nao_podre", good), (start, days, "A", "caju", "podre", rot)]
    g = FA.growth(FA.to_events(expand(spec, rng)), "month")
    check("empty month kept as a zero row", g["good"].tolist() == [100, 0, 50, 60] and g["rotten"].tolist() == [0, 0, 20, 30], g[["good", "rotten"]].values.tolist())
    rc = g["rotten_count_growth"].to_numpy()
    gc = g["good_count_growth"].to_numpy()
    rp = g["rotten_prop_growth"].to_numpy()
    check("previous=0 -> NaN (rotten Feb, Mar; good Mar)", np.isnan(rc[1]) and np.isnan(rc[2]) and np.isnan(gc[2]), f"rotten={rc.tolist()} good={gc.tolist()}")
    check("into an empty period: good growth = -100%", gc[1] == -1.0, gc[1])
    check("normal case exact: rotten Apr +50%, good Apr +20%", abs(rc[3] - 0.5) < 1e-12 and abs(gc[3] - 0.2) < 1e-12)
    check("proportion growth Apr = (1/3)/(2/7)-1 = 1/6", abs(rp[3] - 1 / 6) < 1e-12 and np.isnan(rp[1]) and np.isnan(rp[2]), rp.tolist())
    check("no inf anywhere in growth table", not np.isinf(g.select_dtypes("number").to_numpy(dtype=float)).any())


def test_fruit_counts(seed=0):
    rng = np.random.default_rng(seed)
    (jan, jd), (feb, fd) = month(0), month(1)
    spec = [(jan, jd, "A", "caju", "nao_podre", 500), (jan, jd, "A", "castanha", "nao_podre", 300), (jan, jd, "A", "melao", "podre", 900),
            (feb, fd, "A", "caju", "nao_podre", 2000), (feb, fd, "A", "castanha", "podre", 100)]
    e = FA.to_events(expand(spec, rng))
    full = FA.fruit_counts(e)
    janc = FA.fruit_counts(e, "2024-01-01", "2024-02-01")
    febc = FA.fruit_counts(e, "2024-02-01", "2024-03-01")
    none = FA.fruit_counts(e, "2025-01-01", "2025-02-01")
    check("whole range counts exact, caju first", full["n"].to_dict() == {"caju": 2500, "melao": 900, "castanha": 400}, full["n"].to_dict())
    check("shares sum to 1", abs(full["share"].sum() - 1) < 1e-12)
    check("January window -> melao top (900)", janc.index[0] == "melao" and janc["n"].iloc[0] == 900, janc["n"].to_dict())
    check("February window keeps melao with 0", febc.loc["melao", "n"] == 0, febc["n"].to_dict())
    check("empty window -> all 0, share NaN", (none["n"] == 0).all() and none["share"].isna().all(), none.to_dict())


def gauss_events(seed, weeks=104, n=500):
    rng = np.random.default_rng(seed)
    p = {"A": np.clip(rng.normal(0.20, 0.04, weeks), 0, 1), "B": np.clip(rng.normal(0.35, 0.06, weeks), 0, 1), "C": rng.beta(0.4, 12, weeks)}
    spec = []
    for s, ps in p.items():
        for w in range(weeks):
            r = rng.binomial(n, ps[w])
            spec += [(week(w), 7, s, "caju", "podre", r), (week(w), 7, s, "caju", "nao_podre", n - r)]
    return FA.to_events(expand(spec, rng))


def test_gaussian_known():
    n = 500
    truth = {"A": (0.20, 0.04), "B": (0.35, 0.06)}
    e = gauss_events(0)
    props, _ = FA.sector_proportions(e, "week")
    fit = FA.gaussian_fit(props)
    print(fit.round(4).to_string())
    for s, (mu, sd) in truth.items():
        sd_eff = np.sqrt(sd ** 2 + (mu * (1 - mu) - sd ** 2) / n)
        r = fit.loc[s]
        check(f"sector {s}: mean within 0.01 of {mu}", abs(r["mean"] - mu) < 0.01, f"mean={r['mean']:.4f}")
        check(f"sector {s}: std within 15% of sqrt(sigma^2 + binomial) = {sd_eff:.4f} (sigma={sd})",
              abs(r["std"] - sd_eff) / sd_eff < 0.15, f"std={r['std']:.4f}")
        check(f"sector {s}: n=104 (seed 0 flag: {r['reason']}; judged by the 20-seed rate below)", r["n"] == 104)
    check("sector C (skewed Beta near 0): flagged", bool(fit.loc["C", "flagged"]), fit.loc["C", "reason"])
    flags = {"A": 0, "B": 0, "C": 0}
    seeds = range(20)
    for seed in seeds:
        p, _ = FA.sector_proportions(gauss_events(seed), "week")
        f = FA.gaussian_fit(p)
        for s in flags:
            flags[s] += bool(f.loc[s, "flagged"])
    print(f"    flags over 20 seeds: {flags} (expected for true Gaussians ~1/20 from Shapiro alpha=0.05)")
    check("true Gaussian sectors flagged <= 4/20 each", flags["A"] <= 4 and flags["B"] <= 4, flags)
    check("skewed sector flagged >= 19/20", flags["C"] >= 19, flags)
    small = FA.gaussian_fit(props.iloc[:10])
    check("10 periods -> flagged 'n<20'", small["flagged"].all() and small["reason"].str.contains("n<20").all(), small["reason"].tolist())


def trend_events(seed, weeks=30, n=1000):
    rng = np.random.default_rng(seed)
    spec = []
    for w in range(weeks):
        for s, p in (("rising", 0.20 + 0.019 * w), ("flat", 0.10)):
            r = rng.binomial(n, p)
            spec += [(week(w), 7, s, "caju", "podre", r), (week(w), 7, s, "caju", "nao_podre", n - r)]
        if w >= weeks - 5:
            r = rng.binomial(n, 0.3)
            spec += [(week(w), 7, "short", "caju", "podre", r), (week(w), 7, "short", "caju", "nao_podre", n - r)]
    return FA.to_events(expand(spec, rng))


def test_forecast_known_trend():
    fc = FA.forecast(trend_events(0), "week")
    print(fc.drop(columns=["intercept"]).round(4).to_string())
    r, f, s = fc.loc["rising"], fc.loc["flat"], fc.loc["short"]
    check("rising: slope within 0.002 of true 0.019", abs(r["slope"] - 0.019) < 0.002, f"slope={r['slope']:.5f}")
    check("rising: next-week prediction within 0.03 of true 0.77", abs(r["rotten_pred"] - 0.77) < 0.03, f"pred={r['rotten_pred']:.4f}")
    check("rising: true 0.77 inside 95% PI", r["rotten_lo"] <= 0.77 <= r["rotten_hi"], f"[{r['rotten_lo']:.4f}, {r['rotten_hi']:.4f}]")
    check("rising: P(more rotten than good) > 0.95", r["p_more_rotten"] > 0.95, f"{r['p_more_rotten']:.4f}")
    check("flat: prediction within 0.02 of 0.10 and P(more rotten) < 0.01", abs(f["rotten_pred"] - 0.10) < 0.02 and f["p_more_rotten"] < 0.01,
          f"pred={f['rotten_pred']:.4f} P={f['p_more_rotten']:.2e}")
    check("short (5 periods < 8): 'insufficient data', no numbers", s["status"] == "insufficient data" and np.isnan(s["rotten_pred"]) and np.isnan(s["p_more_rotten"]), s["status"])
    check("rolling origin: 30-8 = 22 origins", r["bt_origins"] == 22 and f["bt_origins"] == 22, r["bt_origins"])
    check("backtest MAE < 0.03 on both sectors", r["bt_mae"] < 0.03 and f["bt_mae"] < 0.03, f"rising {r['bt_mae']:.4f} flat {f['bt_mae']:.4f}")
    cover = []
    for seed in range(1, 11):
        x = FA.forecast(trend_events(seed), "week")
        cover += [x.loc["rising", "bt_coverage"], x.loc["flat", "bt_coverage"]]
    cov = float(np.mean(cover))
    check("pooled backtest 95% PI coverage over 10 seeds in [0.88, 0.99]", 0.88 <= cov <= 0.99, f"coverage={cov:.3f} (440 one-step forecasts)")
    exact = FA.forecast(trend_events(0, weeks=8), "week", min_periods=8)
    check("exactly min_periods -> forecast ok but 0 backtest origins", (exact.loc[["rising", "flat"], "status"] == "ok").all() and (exact.loc[["rising", "flat"], "bt_origins"] == 0).all())
    try:
        FA.forecast(trend_events(0), "week", min_periods=2)
        check("min_periods < 3 rejected", False)
    except ValueError:
        check("min_periods < 3 rejected", True)


def test_single_sector():
    e = gauss_events(0)
    e = e[e["sector"] == "A"].reset_index(drop=True)
    props, _ = FA.sector_proportions(e, "week")
    fc = FA.forecast(e, "week")
    fit = FA.gaussian_fit(props)
    check("single sector: forecast has 1 row, status ok", list(fc.index) == ["A"] and fc.loc["A", "status"] == "ok")
    check("single sector: gaussian has 1 row", list(fit.index) == ["A"] and fit.loc["A", "n"] == 104)
    check("single sector: growth and recurrence run", len(FA.growth(e, "week")) == 104 and len(FA.recurring_growth(e, "month")) == 12)


def test_recurring_known_pattern(seed=0):
    rng = np.random.default_rng(seed)
    good_l = {1: 1200, 2: 1440, 3: 1728}
    rot_l = {7: 130, 8: 169, 9: 220}
    spec = []
    for m in range(36):
        start, days = month(m)
        spec.append((start, days, "A", "caju", "nao_podre", good_l.get(start.month, 1000)))
        spec.append((start, days, "A", "caju", "podre", rot_l.get(start.month, 100)))
    e = FA.to_events(expand(spec, rng))
    mt = FA.recurring_growth(e, "month")
    exp_good = {1: 0.2, 2: 0.2, 3: 0.2, 4: 1000 / 1728 - 1}
    exp_rot = {7: 0.3, 8: 0.3, 9: 220 / 169 - 1, 10: 100 / 220 - 1}
    eg = max(abs(mt.loc[k, "good_median_growth"] - exp_good.get(k, 0.0)) for k in range(1, 13))
    er = max(abs(mt.loc[k, "rotten_median_growth"] - exp_rot.get(k, 0.0)) for k in range(1, 13))
    check("month buckets: good median growth exact (Jan-Mar +20%, Apr -42.1%)", eg < 1e-12, f"max err {eg:.1e}")
    check("month buckets: rotten median growth exact (Jul/Aug +30%, Sep +30.2%, Oct -54.5%)", er < 1e-12, f"max err {er:.1e}")
    check("month buckets: rotten growth peak in September", mt["rotten_median_growth"].idxmax() == 9, mt["rotten_median_growth"].idxmax())
    check("month buckets: January has n=2 (first Jan has no previous)", mt.loc[1, "good_n"] == 2 and mt.loc[2, "good_n"] == 3)
    st = FA.recurring_growth(e, "season")
    exp_sg = {"summer": 4368 / 3000 - 1, "autumn": 3000 / 4368 - 1, "winter": 0.0, "spring": 0.0}
    exp_sr = {"summer": 0.0, "autumn": 0.0, "winter": 519 / 300 - 1, "spring": 300 / 519 - 1}
    es = max(max(abs(st.loc[k, "good_median_growth"] - v) for k, v in exp_sg.items()), max(abs(st.loc[k, "rotten_median_growth"] - v) for k, v in exp_sr.items()))
    check("season buckets (astronomical, Southern Hemisphere): exact", es < 1e-12 and list(st.index) == ["summer", "autumn", "winter", "spring"], st.round(4).to_dict())
    ceara = {m: "rainy" if 2 <= m <= 5 else "dry" for m in range(1, 13)}
    ct = FA.recurring_growth(e, "season", ceara)
    exp_c = {"rainy": 5168 / 8200 - 1, "dry": 8200 / 5168 - 1}
    ec = max(abs(ct.loc[k, "good_median_growth"] - v) for k, v in exp_c.items())
    check("swapped SEASONS constant (Ceara rainy Feb-May / dry): exact", ec < 1e-12 and list(ct.index) == ["dry", "rainy"], ct.round(4).to_dict())
    wt = FA.recurring_growth(e, "week")
    check("week-of-year buckets: keys in 1..53, <=3 periods per bucket (structural only)",
          set(wt.index) <= set(range(1, 54)) and wt["good_n"].max() <= 3, f"{len(wt)} buckets")


def demo_events(seed=0, weeks=104, n=400):
    rng = np.random.default_rng(seed)
    kinds = ["podre", "queimada", "quebrada"]
    fruits = ["caju", "castanha", "melao"]
    spec = []
    for w in range(weeks):
        p = {"north": float(np.clip(rng.normal(0.20, 0.04), 0, 1)), "south": 0.10 + 0.005 * w, "hills": rng.beta(0.4, 12)}
        mix = np.roll([0.6, 0.25, 0.15], (w // 13) % 3)
        for s, ps in p.items():
            total = rng.poisson(n)
            r = rng.multinomial(rng.binomial(total, ps), mix)
            for k, c in zip(kinds, r):
                spec += [(week(w), 7, s, f, k, x) for f, x in zip(fruits, rng.multinomial(c, [0.5, 0.3, 0.2]))]
            spec += [(week(w), 7, s, f, "nao_podre", x) for f, x in zip(fruits, rng.multinomial(total - r.sum(), [0.5, 0.3, 0.2]))]
    return expand(spec, rng)


def test_charts():
    raw = demo_events()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "records.csv")
        raw.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%S")
        e = FA.load_events(path)
    res = FA.run(e, DEMO_DIR, "week")
    names = sorted(f for f in os.listdir(DEMO_DIR) if f.endswith(".png"))
    check("7 PNG charts written (items 1-7)", len(names) == 7, names)
    for f in names:
        im = Image.open(os.path.join(DEMO_DIR, f))
        dpi = im.info.get("dpi", (0, 0))
        corner = im.convert("RGB").getpixel((2, 2))
        check(f"{f}: 300 DPI, white background", abs(dpi[0] - 300) < 1 and corner == (255, 255, 255), f"dpi={dpi[0]:.1f} size={im.size} corner={corner}")
    print(res["forecast"][["status", "n_periods", "rotten_pred", "rotten_lo", "rotten_hi", "p_more_rotten", "bt_mae", "bt_naive_mae", "bt_coverage"]].round(3).to_string())
    print(res["gaussian"][["n", "mean", "std", "shapiro_p", "mass_outside_01", "flagged", "reason"]].round(4).to_string())


if __name__ == "__main__":
    for t in (test_records_roundtrip, test_dominant_deformity, test_growth_known_rate, test_previous_zero_and_empty_period, test_fruit_counts,
              test_gaussian_known, test_forecast_known_trend, test_single_sector, test_recurring_known_pattern, test_charts):
        print(f"\n== {t.__name__}")
        t()
    failed = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED:", failed)
        sys.exit(1)
