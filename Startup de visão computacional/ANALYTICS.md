# FruitCam AI: statistical analytics layer

This document explains `fruit_analytics.py` and `test_fruit_analytics.py`. It starts with the basic ideas (what a histogram, a growth rate, a Gaussian and a forecast interval are) and ends with the code, function by function. The code itself has no comments; this file is the only place where it is explained.

**Status:** everything below was verified on **synthetic data only**. No real detection log exists in the project yet, so none of these numbers say anything about real sectors, fruit or seasons.

---

## Part 0: what a detection record contains today

I read the source directly. The only code that writes a detection record is `infer.py` (when run with `--log`), through `records.py`:

| Column | Source | Notes |
|---|---|---|
| `timestamp` | `datetime.now()` at prediction time, `infer.py:52` | Local machine clock, no timezone, ISO format to the second |
| `sector` | `--sector` CLI argument | Free text typed by the operator |
| `fruit` | `--fruit` CLI argument | Free text typed by the operator, **not** predicted by the model |
| `label` | model output (`predict`) | The class with the highest softmax probability |
| `confidence` | model output | That class's softmax probability |
| `lot` | `--lot` CLI argument | Optional, empty by default |

`infer.py` refuses `--log` unless `--sector` and `--fruit` are also given (`infer.py:45-46`).

What this means for the analytics:

- **The event table needs no logging change.** `timestamp`, `sector` and `fruit_type` are logged directly. `is_good` and `deformity_type` are derived from `label`: a fruit is good if `label` is in `GOOD_LABELS = ("nao_podre",)`; otherwise it is rotten and `deformity_type = label`.
- **There is no deformity information in the current model.** `model.pt` was trained with exactly two classes, `['nao_podre', 'podre']` (I checked by loading the checkpoint; `crop_dataset.py:61` maps YOLO class 5 → `podre` and 4 → `nao_podre`). On real data today, item 1 (deformity predominance) will always report `podre`. The analytics code is ready for more types: once the model is retrained with classes like `queimada` or `quebrada`, every non-good label automatically becomes a deformity type. Producing those types is a model and data job, not a logging job, and I did not touch `train.py` or the model.
- **`visualize.py` does not log anything.** It calls `predict` and draws a box, but writes no record. Only detections made through `infer.py --log` reach the analytics. If the cameras run through `visualize.py`, they need the same three-line logging call; I did not add it because you didn't ask for that path.
- **Sector and fruit are typed by hand.** A typo (`melão` vs `melao`, `Norte` vs `norte`) creates a separate sector or fruit in every statistic. `FRUIT_TYPES` uses `melao`, without the accent.
- `confidence` is not used by the analytics. Every prediction counts, however unsure the model was.

**Changes to existing files: none.** See the last section.

---

## Part 1: the concepts, from simplest to the ones the code relies on

### 1.1 Counts and proportions

A **count** is how many fruits fell into a group, for example 120 rotten caju in week 14. A **proportion** is a count divided by the total, for example 120 rotten out of 600 inspected, which is 0.20 or 20%.

The two answer different questions. If a sector doubles its deliveries, rotten *counts* double even if quality did not change; the rotten *proportion* stays the same. That is why items 4 and 5 report both.

### 1.2 Periods

A **period** is a time bucket: a week (Monday to Sunday), a calendar month, or a season. Every statistic here first groups fruits into periods.

A period with zero fruits is still a period. The code keeps it as a row of zeros instead of silently skipping it. Otherwise "growth from week 11 to week 12" could quietly turn into growth from week 11 to week 13.

### 1.3 Growth rate

The period-over-period growth rate is

```
growth = (current - previous) / previous
```

Going from 100 to 120 is +0.20 (+20%). Going from 100 to 0 is −1.0 (−100%).

**If `previous = 0`, the growth is undefined:** you cannot divide by zero. Some tools return infinity, others return 0. Both are wrong: infinity breaks every chart and average, and 0 claims "no change" when there was a change. This code returns **NaN** (not-a-number, meaning "no value"), which charts draw as a gap.

### 1.4 Histogram

A **histogram** splits a range of values into bins and draws one bar per bin, with height equal to how many values landed in it. It shows the *shape* of data: where values cluster, whether they are symmetric, whether there are outliers.

Item 6 uses the same idea over *categories* instead of numeric bins. Each bar is a recurring calendar bucket (week-of-year 1–53, month 1–12, or season), and its height is the growth observed in that bucket.

### 1.5 Mean, standard deviation, median

- **Mean:** the average.
- **Standard deviation (std):** the typical distance of values from the mean. A small std means the values are tightly packed.
- **Median:** the middle value once sorted. It is barely affected by one extreme value, whereas the mean is. Growth rates produce extreme values easily (a week going from 3 to 12 rotten fruits is +300%), so item 6 uses medians.

### 1.6 The Gaussian (normal) distribution

The **Gaussian** is the bell curve. It is fully described by two numbers, mean and std. About 68% of values fall within 1 std of the mean and about 95% within 2 std. Fitting a Gaussian means estimating that mean and std from data and then asking whether the bell shape actually describes the data.

**Why it is risky for proportions:** a proportion can only be between 0 and 1, but a bell curve extends from −∞ to +∞. If a sector's rotten rate averages 0.03 with std 0.04, the fitted curve puts a real chunk of its probability below zero, which is impossible. The code computes that impossible mass and flags the fit when it exceeds 1%.

### 1.7 Checking normality: Shapiro-Wilk and the Q-Q plot

- **Shapiro-Wilk test:** returns a p-value. A small p-value (< 0.05) means "data this far from a bell shape would be unusual if the data really were Gaussian", so we flag it. A large p-value does **not** prove the data is Gaussian; it only means the test could not detect a departure. With few periods it almost never can, which is why fewer than 20 periods is also flagged.
- By design, the test wrongly flags a *truly* Gaussian sector about 5% of the time (α = 0.05). This happened in the test suite (see Part 4); it is expected behavior, not a bug.
- **Q-Q plot:** sorts the observed values and plots them against where a perfect Gaussian would put them. If the data is Gaussian, the points lie on a straight line. Curves at the ends reveal skew or heavy tails, and a flat row of points at 0 reveals a floor effect.

### 1.8 Sampling noise in a proportion

Even if a sector's true rotten rate is exactly 20% every week, a week of 500 fruits will not show exactly 100 rotten; it might show 92 or 109. That binomial noise adds variance:

```
observed variance ≈ true variance between weeks + p(1-p)/n
```

So the std this code reports is the std of *observed* weekly proportions, which is slightly larger than the "true" week-to-week std. The tests account for this explicitly.

### 1.9 Linear trend and forecasting

A **linear trend** fits a straight line `proportion = intercept + slope × period` through past points (ordinary least squares). Extending the line one period ahead gives a **point forecast**.

### 1.10 Prediction interval

A point forecast alone hides the uncertainty. A **95% prediction interval** is a range that should contain the next observed value about 95% of the time *if the model is right*. It widens when past points scatter around the line, when there are few periods, and when the forecast lies far from the middle of the data.

From the same uncertainty we get **P(rotten > good next period)**: the probability, under the model, that the next rotten proportion exceeds 0.5. That is the item-2 answer, given as a probability instead of a bare yes/no.

### 1.11 Backtesting with a rolling origin

To check whether a forecaster works, pretend you are in the past. Fit on periods 1–8 and forecast 9, then fit on 1–9 and forecast 10, and so on. Each forecast is compared with what actually happened. This yields:

- **MAE** (mean absolute error): the average size of the miss.
- **Naive MAE:** the same, for the dumbest possible forecast, "next period = this period". If the linear model does not beat it, it adds nothing.
- **Coverage:** the fraction of real values that fell inside the 95% interval. It should be near 0.95.
- **Direction accuracy:** how often the model correctly said whether rotten would exceed 50%.

---

## Part 2: assumptions and definitions (read before trusting any chart)

1. **"Importado" means "received by the system".** Item 3 counts fruits that went through the camera and were logged, not fruit imported from another country.
2. **Good vs rotten** comes only from the model's prediction. Misclassifications flow straight into every statistic. The analytics measures *what the model said*, not ground truth.
3. **Growth is computed on both counts and proportions**, with the same formula `(current - previous) / previous`, in clearly separated columns: `good_count_growth`, `good_prop_growth`, `rotten_count_growth`, `rotten_prop_growth`. Proportion growth is a *relative* change of a proportion: 20% → 25% is +0.25, not +5 percentage points.
4. **Previous = 0 → NaN.** Never inf, never 0.
5. **The item-2 forecast uses the rotten proportion, not the good/rotten ratio.** The ratio good/rotten is undefined whenever a period has no rotten fruit, and it is unbounded. The rotten proportion `p` carries the same information ("more rotten than good" ⇔ `p > 0.5`) and is always defined.
6. **Seasons:** the default `SEASONS` maps each month to the Southern Hemisphere astronomical season covering most of its days (Jan–Mar summer, Apr–Jun autumn, Jul–Sep winter, Oct–Dec spring). That is an approximation, since astronomical seasons start around the 21st. To use Ceará's rainy/dry seasons, replace the constant, for example:
   ```python
   SEASONS = {m: "rainy" if 2 <= m <= 5 else "dry" for m in range(1, 13)}
   ```
   The test suite runs exactly this swap.
7. **Partial periods distort growth.** If logging starts on a Thursday, the first week holds only 4 days and the growth into week 2 looks inflated. The same applies to the last period and to the first season (the Ceará test shows a +331% artifact from a one-month "dry" season at the start). Filter the data to whole periods before reading the first and last bars.
8. **Weeks or months with fewer than `MIN_FRUITS = 30` fruits** in a sector are excluded from that sector's forecast and Gaussian fit, because their proportion is too noisy. They still count in items 1, 3, 4, 5 and 6.

---

## Part 3: the code, function by function

Everything lives in [fruit_analytics.py](fruit_analytics.py), as plain functions on pandas DataFrames.

### Constants ([lines 13–37](fruit_analytics.py#L13-L37))

- `GOOD_LABELS`: model labels that count as good.
- `FRUIT_TYPES`: always shown in item 3, even with 0 fruits.
- `SEASONS`: the single month→season mapping.
- `MIN_PERIODS = 8`: the minimum number of periods for a forecast.
- `MIN_FRUITS = 30`: the minimum number of fruits for a period to enter the forecast or Gaussian fit.
- `MIN_GAUSS_N = 20`, `ALPHA = 0.05`, `MAX_OUTSIDE = 0.01`: the Gaussian flag thresholds.
- Colors: blue = good, orange = rotten. They are distinguishable under red-green colorblindness, unlike green/red. I checked them with a palette validator.
- `DPI = 300`.

### Building the event table

- **[`to_events(raw)`](fruit_analytics.py#L40):** turns the `records.py` CSV columns into the event table `timestamp, sector, fruit_type, is_good, deformity_type`. It raises an error on missing columns, an empty table, or nulls. `deformity_type` is NaN for good fruit.
- **[`load_events(path)`](fruit_analytics.py#L60):** reads the CSV and calls `to_events`.

### Period counting (shared by items 4, 5, 6)

- **[`counts(events, period)`](fruit_analytics.py#L64):** one row per period, with columns `good` and `rotten`. It reindexes to the full period range so that empty periods appear as zeros. For `period="season"`, it counts by month, labels each month with its season, and merges *consecutive* months with the same season into one row indexed by its first month. That way "summer 2025" and "summer 2026" stay separate periods, and any `SEASONS` mapping works, including two-season ones.
- **[`rel_change(s)`](fruit_analytics.py#L78):** `(s - previous) / previous`, where a previous value of 0 is replaced by NaN before dividing. This one line implements the previous = 0 rule.

### Item 4 and 5: growth

- **[`growth(events, period)`](fruit_analytics.py#L83):** adds `total`, `good_prop` and `rotten_prop` (NaN when the total is 0), then the four growth columns. Good growth (item 4) and rotten growth (item 5) come from the same table.

### Item 6: recurring growth

- **[`bucket(index, period)`](fruit_analytics.py#L95):** maps each period to its recurring bucket: ISO week-of-year, month number, or season name.
- **[`recurring_growth(events, period)`](fruit_analytics.py#L103):** takes the count growth from `growth` at that granularity (week-over-week for weeks, month-over-month for months, season-over-season for seasons) and reports the **median** growth per bucket plus `n`, the number of periods behind each bar. With one year of data each bar rests on a single period, so a "recurring" pattern needs at least two or three years before it means anything.

### Item 1: weekly deformity predominance

- **[`deformity_counts(events)`](fruit_analytics.py#L117):** a week × deformity-type table of rotten-fruit counts, including weeks with zero rotten fruit.
- **[`dominant_deformity(t)`](fruit_analytics.py#L127):** for each week, reports `dominant` (the most frequent type, or `none` if there was no rotten fruit), `share` (its fraction of that week's rotten fruit), `n_rotten`, and `tie`. On an exact tie, `dominant` shows the first type alphabetically, so check `tie` before quoting it.

### Item 3: fruit received by type

- **[`fruit_counts(events, start, end)`](fruit_analytics.py#L140):** counts and shares by fruit type within `[start, end)`, sorted by count. All `FRUIT_TYPES` appear even when they have 0 fruits. An empty window returns all zeros with NaN shares.

### Item 2: per-sector forecast

- **[`sector_proportions(events, period)`](fruit_analytics.py#L151):** a period × sector table of rotten proportions, NaN where a sector had fewer than `MIN_FRUITS` fruits.
- **[`linear_fit(t, y, t_new)`](fruit_analytics.py#L160):** least-squares line plus the standard error of a *new observation* at `t_new`. That is the textbook prediction-interval formula `s·√(1 + 1/n + (t_new − t̄)²/Σ(t − t̄)²)`, with `n − 2` degrees of freedom. `t` is the real period position, so skipped low-volume periods don't compress the time axis.
- **[`p_above_half(mean, se, dof)`](fruit_analytics.py#L170):** P(next rotten proportion > 0.5) from the Student-t predictive distribution.
- **[`backtest(t, v)`](fruit_analytics.py#L176):** the rolling-origin evaluation from 1.11. It refits at every origin from `MIN_PERIODS` onward and returns `bt_origins`, `bt_mae`, `bt_naive_mae`, `bt_coverage` and `bt_direction_acc`.
- **[`forecast(events, period)`](fruit_analytics.py#L196):** for each sector with fewer than `min_periods` usable periods, returns `status = "insufficient data"` and NaN for every number. Otherwise it returns the slope, the clipped point forecast and the 95% interval (`rotten_lo`, `rotten_hi`), `p_more_rotten`, and the backtest metrics. P(good > bad) is simply `1 − p_more_rotten`. A `min_periods` below 3 is rejected, because the interval needs at least one degree of freedom.
  - Limitations: a straight line on a bounded quantity will eventually predict below 0 or above 1. The point forecast and interval are clipped to [0, 1]; the probability uses the unclipped values. Seasonality is ignored. Weeks are weighted equally regardless of volume.

### Item 7: Gaussian per sector

- **[`gaussian_fit(props)`](fruit_analytics.py#L223):** per sector, reports `n`, `mean`, `std`, Shapiro-Wilk `W` and `p`, and `mass_outside_01` (the fitted curve's probability below 0 or above 1). `flagged` is True with a readable `reason` if any of these hold: `n < 20`, std is zero or undefined, Shapiro p < 0.05, or mass outside [0, 1] > 1%. **The fit assumes periods are independent draws with no trend.** A sector whose rate is trending (like `south` in the demo) will be flagged or will show an inflated std. Its Gaussian describes the period it was measured over, not a stable property of the sector.

### Item 8: charts

- `_fig`, `_xticks`, `_prob`, `_save` are small helpers: white background, light horizontal grid, readable date ticks, probabilities shown as "> 0.99" / "< 0.01" instead of a misleading "1.00", and saving PNGs at 300 DPI.
- One chart per item:

| File | Function | What it shows |
|---|---|---|
| `1_deformity_weekly.png` | [`plot_deformity`](fruit_analytics.py#L279) | Stacked weekly share of each deformity type among rotten fruit |
| `2_sector_forecast.png` | [`plot_forecast`](fruit_analytics.py#L299) | One panel per sector: observed proportion, trend line, next-period forecast with 95% PI, a dashed line at 50%, and P(rotten > good) plus backtest MAE in the title |
| `3_fruit_counts.png` | [`plot_fruit_counts`](fruit_analytics.py#L330) | Bars by fruit type, labeled with count and share |
| `4_good_growth.png` / `5_rotten_growth.png` | [`plot_growth`](fruit_analytics.py#L344) | Count growth (solid) and proportion growth (dashed, hollow markers) per period. Gaps mean NaN. |
| `6_recurring_growth.png` | [`plot_recurring`](fruit_analytics.py#L360) | Three panels (week-of-year, month, season) of median good/rotten count growth, with the periods-per-bar range in each title |
| `7_sector_gaussian.png` | [`plot_gaussian`](fruit_analytics.py#L376) | Per sector: histogram with the fitted Gaussian (dotted lines at 0 and 1) and a Q-Q plot with Shapiro W/p. The flag reason is in the title. |

### Running it

- **[`run(events, out_dir, ...)`](fruit_analytics.py#L405)** computes every table and writes the seven PNGs.
- **[`main()`](fruit_analytics.py#L428)** is the command line:

```
python infer.py model.pt foto.jpg --log records.csv --sector norte --fruit caju
python fruit_analytics.py records.csv analytics_out --period week
```

Options: `--period month`, `--min-periods N`, `--min-fruits N`, and `--start/--end` (applied to item 3).

---

## Part 4: verification

The test file is [test_fruit_analytics.py](test_fruit_analytics.py). The full executed output is saved in [test_fruit_analytics_output.txt](test_fruit_analytics_output.txt).

How the tests work: `expand()` turns a table of *known* counts into one row per fruit with random timestamps inside each period, exactly like the real log. The tests then run the public functions on those rows and compare the results with the truth that was put in.

**Result: 64/64 checks passed** (Python 3.13, pandas 2.3.3, scipy 1.17.1, matplotlib 3.10.8; about 19 s).

| Test | Ground truth | Recovered | Tolerance |
|---|---|---|---|
| Record round-trip | 3 rows written with `records.append_record` | correct columns, `is_good`, `deformity_type` | exact |
| Dominant deformity | 18 weeks with a known dominant type at 60% | 18/18 correct; max \|share − 0.60\| = 0.053 | 0.10 |
| Count growth | good +10%/month, rotten +20%/month | max error 3.4e-5 and 3.9e-4 (integer rounding) | 0.001 |
| Proportion growth | analytic formula | max error 3.0e-4 | 0.001 |
| previous = 0 / empty month | Jan 100/0, Feb empty, Mar 50/20, Apr 60/30 | NaN exactly where previous = 0; −100% into the empty month; Apr +50%, +20%, 1/6 exact; no inf anywhere | 1e-12 |
| Fruit counts | 2500 / 900 / 400; Jan window led by melao | exact; empty window → zeros and NaN shares | exact |
| Gaussian A (μ = 0.20, σ = 0.04) | mean 0.20, observed std 0.0438 | 0.2032, 0.0389 (11% low) | 0.01; 15% |
| Gaussian B (μ = 0.35, σ = 0.06) | mean 0.35, observed std 0.0636 | 0.3467, 0.0595 | 0.01; 15% |
| Flag rate over 20 seeds | A, B Gaussian; C skewed Beta | A 0/20, B 2/20 flagged; C 20/20 flagged | ≤ 4/20; ≥ 19/20 |
| Forecast, rising sector | slope 0.019, next p = 0.77 | slope 0.01907, forecast 0.7691, PI [0.734, 0.804], P > 0.99 | 0.002; 0.03; truth inside PI |
| Forecast, flat sector | p = 0.10 | 0.1032, P < 0.01 | 0.02 |
| Forecast with 5 periods | below minimum | `insufficient data`, all NaN | exact |
| Backtest | 30 weeks → 22 origins | MAE 0.014 / 0.010 (naive 0.023 / 0.014) | < 0.03 |
| PI calibration | 440 one-step forecasts over 10 seeds | coverage 0.934 | [0.88, 0.99] |
| Recurring by month / season | known monthly levels over 3 years | exact (Sep has the rotten peak; summer good +45.6%, winter rotten +73%) | 1e-12 |
| `SEASONS` swap to Ceará | rainy Feb–May / dry | exact, including the partial-season artifact | 1e-12 |
| Single sector | one sector only | forecast, Gaussian, growth and recurrence all run | — |
| Charts | — | 7 PNGs, 300.0 DPI, white corner pixel | exact |

What happened during verification:

- **First run: 63/64.** Gaussian sector B (truly Gaussian) got Shapiro p = 0.041 on seed 0 and was flagged. That is the 5% false-alarm rate described in 1.7, so the *test* was wrong to demand "not flagged" on a single draw. I removed that single-seed assertion and judge it by the flag rate over 20 seeds (seed 0 included), which is the statistically correct check. I did not change the seed to make it pass.
- **Not tested numerically:** the week-of-year buckets of item 6 were only checked structurally (keys 1–53, at most 3 periods per bucket). With fruit spread randomly inside months, weekly growth is too noisy for a clean ground truth at that size. The visual appearance of the charts was checked by eye, not by a test.
- The pre-existing `logs/test_infer_log.py` (which tests `infer.py --log`) fails as-is with `ModuleNotFoundError: No module named 'infer'`, because it now lives in `logs/` while `infer.py` is in the project root. With the root on the path (`PYTHONPATH=.. python test_infer_log.py`) it passes, so the logging path itself works. I did not modify that file.

---

## Part 5: what this does and does not tell you

**Verified, on synthetic data:** the code computes what it claims. Given data with a known growth rate, dominant deformity, Gaussian parameters or linear trend, it recovers them within the tolerances above. It handles empty periods, previous = 0, a single sector, and too few periods without inventing numbers. Its 95% intervals cover about 93% of new values when the model's assumptions hold.

**Not validated on real data:**

- There is no real detection log yet, so every chart in `analytics_demo_synthetic/` is synthetic and must not be shown as FruitCam results.
- The forecaster's backtest looked good **because the synthetic data was generated from a straight line plus noise**. Real sectors can have harvest seasonality, sudden shocks and changing volume. On real data, read `bt_mae` against `bt_naive_mae`. If the linear model does not beat the naive one, do not present its forecast.
- With only a few weeks of real logs, the forecast returns `insufficient data` (below 8 periods). Even with 8–20 periods, intervals are wide, Shapiro has almost no power, and recurring patterns rest on one period per bucket. Present those results as descriptive, not as conclusions.
- Every number inherits the classifier's errors. A model that misses 10% of rotten fruit makes every rotten proportion about 10% too low. The model's real-world accuracy per fruit type is not measured here.
- Item 1 cannot say anything about deformity types until the model predicts more classes than `podre`.

---

## Part 6: changes to existing files

**None.** No existing file was modified: `infer.py`, `records.py`, `visualize.py`, `train.py`, the model and the `logs/` folder are all unchanged. The current log already contains every field the analytics needs, and the one missing piece (deformity types) is a model limitation that logging cannot fix.

New files:

- `fruit_analytics.py`: the analytics and charts
- `test_fruit_analytics.py`: the tests
- `test_fruit_analytics_output.txt`: the executed test output
- `ANALYTICS.md`: this document
- `analytics_demo_synthetic/`: the 7 demo PNGs, regenerated on every test run

Note: `logs/` contains an older, separate analytics attempt (`analytics.py`, `charts.py`, `report.py`, `records_synth.py`). It overlaps with this work but differs from it: 150 DPI, no backtest, no Q-Q plot, and growth from weekly data only. I left it untouched. Consider deleting it once you adopt `fruit_analytics.py`, so there is a single source of truth.
