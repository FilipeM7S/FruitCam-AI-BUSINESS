# FruitCam AI: the showcase dataset

`python manage.py seed_showcase` fills the app with synthetic data designed so that **every statistical behaviour the app can display actually occurs** in one dataset: on the Painel, on the Linha page and in the PDF certificate. This file is the presenter's guide: what the story is, which sector or line shows which behaviour, and where to click.

**Status:** every behaviour listed below is checked by automated tests ([core/tests/test_showcase.py](../../core/tests/test_showcase.py)) that run the real analytics code on the generated data. The data is synthetic. It is not a model of any real plant, and nothing in it says anything about real fruit.

---

## 1. Run it

```powershell
$env:DJANGO_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(50))"); $env:DJANGO_HTTPS = "0"
python manage.py seed_showcase
python manage.py runserver 127.0.0.1:8000
```

- **What it replaces:** it deletes **every demo row** (`is_demo`), including those created by `seed_demo` and `seed_line_demo`, and inserts the showcase. Real inspections are never touched.
- **Size and time:** about 163,000 Painel events plus 95,000 camera events, written in roughly 60–90 s on this machine.
- **Login:** it does not create or change users. Log in with any existing account; `adduser` creates one.
- **In the app:** choose **Dados → Demonstração** on the Painel and **Dados → Demonstração** on the Linha page.

| Option | Default | Meaning |
|---|---|---|
| `--weeks` | 156 | Weeks of Painel history (3 years). Fewer weeks remove some behaviours (recurrence needs ≥ 2 years). |
| `--line-hours` | 8 | Camera shift length, ending now. `0` skips camera data. |
| `--seed` | 7 | Random seed. The tests pin seed 7. |

**Seed shortly before presenting.**
- The camera shift ends at the moment you run the command.
- The Linha page shows at most the last 24 hours, so after a day the camera data no longer appears there.
- If you seed early on a Monday (before 08:00), the shift is shortened so it stays inside the current week. That keeps camera traffic out of the complete weeks used by growth and recurrence.

**`db.sqlite3` is tracked in git.** Seeding changes it. Commit it or not on purpose.

---

## 2. The story

A cashew processing plant in Ceará, seen over three years:

- **Harvest season.** Volume peaks from August to December (×2 at the peak), with an off-season in March–July.
- **Rains.** The rainy season (February–May) brings rot outbreaks.
- **Defect types change with the calendar.** Immature fruit (*baixa qualidade*) dominates the start of the harvest, sunburn (*queimada*) the dry peak, mechanical damage (*quebrada*) the busiest weeks, and rot (*podre*) the rains.
- **A one-week maintenance shutdown** in a July in the middle of the three years (July 2025 when seeded in October 2026). No fruit is inspected that week.
- **Seven field sectors** supply the plant, each designed to show one statistical behaviour (section 3).
- **Today's shift** runs on two camera lines, with lot, alarm, stop and review stories (section 4).

---

## 3. Painel: which sector shows what

| Sector | Designed as | Shows |
|---|---|---|
| `norte` | Fixed weekly delivery, rotten share ≈ 17%, pure noise | **Normal curve with no flag** (Shapiro p ≈ 0.7); **reliable forecast** (beats the naive forecast) |
| `sul` | Steady decline from 20% to 60% rotten | **Forecast above 50%** with a chance of more rotten than good **> 99%**; **poor normal fit** (a trend is not a bell curve) |
| `serra` | Almost no rot, with outbreaks in the rains | **Skewed distribution**: Shapiro rejects normality and the fitted curve **spills below 0%** (the hatched "impossível" zone) |
| `leste` | Random walk | Forecast **"não supera a previsão ingênua"** → **não confiável**, with a hatched fan |
| `controle` | Reference samples, always good | **"sem variação"**: no histogram is possible; the flat forecast is also not better than naive |
| `oeste` | New supplier for 15 weeks | Forecast **"menos de 20 períodos"** → não confiável; normal curve flagged **amostra pequena** |
| `vale` | New supplier for exactly 8 weeks | The forecast exists but has **"sem teste retroativo possível"** (8 periods = the minimum, nothing left to backtest) |
| `linha 1`, `linha 2` | Photo sampling for three years before the cameras were installed: rotten share stable near 13% (linha 1) and 18% (linha 2), volume following the harvest. The camera traffic of today's shift is added on top | **Reliable forecast** for both. The normal curve is drawn but flagged **ajuste ruim**: weekly volume swings with the harvest, so the share's spread changes through the year |

**Why the lines have history now.** At first the lines had only today's camera traffic. Every per-sector chart for them then said "Dados insuficientes", which hid most of what the Painel can do.
- **Generation:** their history comes from a **separate random stream** (`line_history`, seed + 3). Every other sector, the tie week, the shutdown and the seasons are identical.
- **Source:** it is stored as photo events (`source = foto`), so the Linha page, which reads only camera events, is unchanged.

Across all sectors:

| Behaviour | Where |
|---|---|
| **Defect dominance changes over the year** (all 4 types dominate some weeks) | Qualidade agora → "Qual defeito domina cada semana?" |
| **A tie between defects** (built on purpose 6 weeks before the seeding week, e.g. 24/08/26) | Same chart and Anexo A.2 of the certificate ("empate") |
| **A week with no rotten fruit** (the shutdown) | Same chart: an "n/d" marker |
| **Growth −100% and then n/d** (previous week was zero) | Tendências → growth charts, the shutdown week and the one after |
| **Incomplete periods excluded** (the data starts on a Thursday) | Badge "Parciais fora" on growth and recurrence |
| **Recurring seasonal growth** (3 periods per month bucket, so no "Amostra pequena") | Tendências → recurrence; month view peaks in Aug–Oct |
| **Seasonality and gaps in volume** | Visão geral → volume; certificate figure "Cobertura dos dados" |
| **Clipped scale** (about 90,000 camera fruits today vs ≈ 2,000 per week) | Visão geral → volume: the "Escala cortada" badge and a callout with the week's real total |

**Tip: switch Período from Semana to Mês.** With monthly periods, `oeste` and `vale` drop below 8 periods and become "dados insuficientes", while `serra` stops beating the naive forecast. That's a good live demonstration that the statistics are honest about sample size.

---

### Sorting: each Painel fruit has a model class and a confidence

Every synthetic Painel fruit now carries the simulated model output (`label`, `confidence`), like the camera events already did. Before, these fields were empty, so there was nothing to sort or to simulate a confidence threshold on.

- **Class:** good fruit is `boa`, *baixa qualidade* and *podre* keep their class. The two defects the model has no class for are sorted into the nearest one: *quebrada* goes to `baixa_qualidade` and *queimada* to `podre`. The defect type stays in `deformity_type`.
- **Confidence:** known classes are confident (median 0.91). *Queimada* and *quebrada* are not (median 0.64), because the model never saw them.
  - This gives a threshold story: at a review threshold of 0.80, 14% of known-class fruit goes to review, against 85% of *queimada*/*quebrada*.
- **Nothing else changes:** the values come from a separate random stream (seed + 2), and the statistics never read these two fields. Every sector, calendar and line behaviour above is identical.
- **Every fruit is still decided:** `needs_review` stays false on Painel events, so the Painel numbers are the same as before.
- **Counts (seed 7, 156 weeks):** boa 128,626; baixa qualidade 16,041 (7,411 + 8,630 quebrada); podre 18,821 (10,710 + 8,111 queimada).

---

## 4. Linha page: the two camera lines

The shift starts on a 5-minute boundary. Lots are 90 minutes long unless stated otherwise.

**Linha 1 · recepção** (2 fruits/s, maximum 18% rotten):
- **Lot 03: rotten jumps to 32%** → **Reprovado**, and the control chart fills with **"acima do limite superior"** alarms; a slow tail also triggers an **"8 janelas seguidas acima da mediana"** alarm.
- **Lot 04: the belt stops for 18 minutes** → a gap in the flow chart and windows with no point on the control chart.
- **Lot 05: rotten exactly at the 18% maximum** → **Inconclusivo** (the 95% interval crosses the limit).

**Linha 2 · seleção** (1.4 fruits/s, maximum 18%):
- **A slow drift of +2.5 points** over about 2.5 hours → **"8 janelas seguidas acima da mediana"** (trend) with few limit crossings.
- **A lighting problem** (32 minutes, 35% of fruit to review) → a pink "Revisar" band in the flow chart, and a higher review share.
- **Lot 02 comes from a supplier with smaller fruit** (−5 mm) → visible in the size distribution.
- **Lot 04 is a 12-minute sample lot** → **Inconclusivo** because the sample is small, not because the fruit is bad.

On the Linha page choose **8 h** to see the whole shift. The **certificate** shows all of it with 5-minute windows, a lot-acceptance chart and a size histogram.

---

## 5. Changes to the Painel made for this

The showcase exposed two places where the Painel did not present the data well. Both are general fixes, not demo-only:

- **Volume chart with an outlier.**
  - **Before:** one week with 40× the usual volume flattened every other bar.
  - **Now:** the scale is cut at 1.6× the 95th percentile, but only when the largest value is more than 3× that percentile. The cut bar carries its value in a callout (e.g. "91.506 ▲ · Escala cortada"), and the card gets an "Escala cortada" badge.
  - **Same rule as the certificate:** `robustLimit` in [series.js](../../frontend/src/series.js) and `robust_limit` in [certificate_charts.py](../../core/certificate_charts.py).
  - **Tested:** a new Node test covers it (52 ordinary weeks are not cut; adding a 91,000 week cuts at exactly 1.6 × the 95th percentile).
- **Many sectors.** The "Taxa de podres por setor" row now grows with the number of sectors (`46 + 22 px` per sector, minimum unchanged), so labels no longer collide. With 5 sectors or fewer nothing changes.
- **Faster loading, identical numbers.**
  - **Before:** `stats.load_events` let Django turn every timestamp into a Python `datetime`, one row at a time.
  - **Now:** it reads the same query through a raw cursor with the timestamp cast to text, and pandas parses all timestamps at once. Loading 255,000 events takes about 1.2 s instead of 2.1–3.4 s.
  - **Same numbers:** the result is identical in 5 filter combinations (DataFrame equality). The certificate fingerprint, a SHA-256 over every statistic, came out byte-identical before and after the change.

---

## 6. Verification

[core/tests/test_showcase.py](../../core/tests/test_showcase.py), with seed 7 and fixed dates:

| Test | Checks |
|---|---|
| Sector states | Every forecast state (reliable, > 99% chance, not better than naive, few periods, no backtest, insufficient data) and every Gaussian state (no flag, not normal, outside 0–100%, small sample, no variance) on the sector designed for it |
| Calendar | A tie week, exactly one empty week, all 4 defect types dominating somewhere, n/d growth right after the shutdown, partial periods excluded, ≥ 2 periods per month bucket, positive growth in Aug–Sep and negative in Jan–Feb |
| Camera lines | Linha 1: one rejected and one inconclusive lot, limit alarms, ≥ 3 empty windows (the stop). Linha 2: the run rule, an inconclusive lot, and a higher review share |
| Sorting | Every Painel fruit has one of the 3 model classes, `boa` exactly when the fruit is good, every *podre* stays `podre`, confidence in [0.34, 1], queimada/quebrada at least 0.2 less confident (median), more than 3× as often sent to review at 0.80, and the output is reproducible |
| Command | Reseeding twice gives the same number of rows; old demo rows are removed; real rows are untouched; both sources (photo and camera) and all 7 field sectors are present; no demo row lacks a class or a confidence |
