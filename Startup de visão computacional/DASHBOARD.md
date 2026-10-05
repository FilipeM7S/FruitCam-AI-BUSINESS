# FruitCam AI: the redesigned dashboard

This document explains the dashboard redesign. It starts with the basic ideas (what a histogram, a bell curve, a confidence band, a growth rate and a Q-Q plot are) and ends with the code, chart by chart. The code has no comments; this file is the only place where it is explained.

**Status:**
- **Synthetic data:** all statistics below were verified with automated tests, on synthetic data with known answers.
- **Browser:** everything visual was checked only in headless Microsoft Edge on this Windows machine.
- **Not tested:** real phones, other browsers, real frame rates and real screens. See Part 8.

---

## Part 0: what the dashboard was before (Step 0, read from the source)

| Item | Before |
|---|---|
| Chart library | Chart.js 4.5.1 (unchanged; still the only chart library) |
| Charts | deformity stacked bars; one forecast chart with floating interval bars across sectors; fruit horizontal bars; two growth line charts; recurrence grouped bars with tabs; Gaussian stepped-line histogram plus Q-Q scatter; overview stacked bars |
| Shown as text instead of a chart | **forecast**: a text list per sector (probability, interval, backtest, reasons); **Gaussian**: mean, std, n and Shapiro result as text lines; **overview**: a `<dl>` grid of five numbers; summary paragraphs under deformity, fruits and both growth cards |
| Animation | Chart.js default 300 ms on creation only. **`ChartBox` destroyed and recreated the chart on every filter change**, so nothing morphed. CSS `rise` fade on cards; a skeleton shimmer that animated `background-position` (not transform or opacity); a global reduced-motion rule that shortened durations but not delays |

---

## Part 1: the concepts, in plain words

- **Bar chart / stacked bar.** A bar's length is a number. A stacked bar splits one bar into colored pieces that add up to the whole. In the deformity chart each week's bar adds up to 100% of that week's rotten fruit.
- **Histogram.** Sort many measurements into bins and draw one bar per bin; the bar's height says how many measurements fell in that bin. It shows the shape of the data: where most values sit, and whether it is symmetric or lopsided.
- **Mean (média) and standard deviation (σ, desvio).** The mean is the average. σ is the typical distance from the mean.
- **Gaussian (normal, bell curve).** A symmetric bell shape fully described by its mean and σ. *If* data were truly normal, about 68% of it would fall within ±1σ of the mean and about 95% within ±2σ. Those are the dark and light bands drawn on the chart.
- **Why a bell curve can be wrong here.** A proportion cannot go below 0% or above 100%, but a bell curve has no limits. When the fitted curve spills past 0% or 100%, the chart draws that region with diagonal hatching and labels it "impossível".
- **Q-Q plot.** Sort the real values and plot each one against where a perfect bell curve would put it. If the data is normal, the points lie on the straight line. Curves at the ends mean the data is lopsided or has extremes.
- **Shapiro-Wilk p-value.** A number from a test of "could this data be normal?". p < 0.05 means "probably not", and the chart then shows **AJUSTE RUIM**. A large p does not prove normality, especially with few periods.
- **Growth rate.** `(this period − previous period) ÷ previous period`. Going from 100 to 120 is +20%.
- **n/d (pt-BR for n/a).** If the previous period was 0 or empty, growth is undefined: you can't divide by zero. The chart draws a small dashed "n/d" marker there, **never a zero bar**, because zero would claim "no change".
- **Median.** The middle value once sorted. The recurrence chart uses it so one wild period doesn't dominate.
- **Forecast and confidence band (leque).** A straight line fitted to a sector's history is extended one period ahead (dashed). The shaded fan is the **95% prediction interval**: if the model's assumptions hold, the next real value lands inside it about 95% of the time. A wider fan means more uncertainty.
- **Sample size n.** How many fruits (or periods) a number is based on. With small n, everything above becomes unreliable, and the charts say so with badges.

---

## Part 2: how each chart explains itself (no text blocks)

Every card has exactly one paragraph of text: a one-sentence subtitle under the question. Everything else is drawn on or next to the chart.

- **The title is a question** the chart answers, e.g. "Qual defeito domina cada semana?"
- **Annotations on the chart itself**, positioned from the chart's own geometry:
  - **deformity:** a callout on the latest week's dominant segment;
  - **forecast:** the forecast value plus "chance de + podres";
  - **fruits:** value labels with the winner marked "mais recebida";
  - **growth:** the last change with an ↑/↓ arrow, plus n/d markers;
  - **recurrence:** callouts on the peak bins;
  - **Gaussian:** the mean, ±1σ/±2σ tags, "impossível", and the poor-fit stamp;
  - **overview:** count-up counters.
- **"Como ler" button.** It plays a 3–4-step tour on top of the chart: a spotlight on one element plus one line of text per step. It advances by itself every 2.8 s, and you can also use the buttons, the ← → keys, Esc to skip, or "Pular".
- **Tooltips** show the exact value and n (e.g. "n = 412 frutas", "n = 3 períodos").
- **Badges** on each card or small chart:
  - **"n = …"** is always there;
  - **"Dados de demonstração"** appears whenever the data is synthetic;
  - **"Amostra pequena"**, **"Não confiável"** or **"Ajuste ruim"** appear when the sample is too small or the fit fails;
  - **"Parciais fora"** appears when incomplete periods at the ends were excluded.
- **Screen readers and keyboard.** Every chart area is focusable (Tab), with `role="img"` and an `aria-label` that states the key finding, e.g. "Caju é a mais recebida: 2.730 frutas (50,4%)."
- **Nothing relies on color alone:**
  - the dominant defect is full color *and* named in a callout;
  - growth direction is shown by bar direction *and* an arrow;
  - a poor fit gets a dashed grey curve *and* the "AJUSTE RUIM" stamp;
  - an unreliable forecast gets a hatched fan *and* a badge.

---

## Part 3: motion

| Where | What moves | How |
|---|---|---|
| Entry | Bars grow, lines and curves sweep left to right, staggered (up to ~28 ms per point, 90 ms per series); cards fade/rise in with 60 ms stagger | Chart.js native animation with a per-point `delay`; CSS `card-in` (transform + opacity) |
| Scroll | Charts below the fold are created only when they come within 120 px of the viewport, so each one plays its entry as you scroll | `IntersectionObserver` in `ChartBox` |
| Filter change (period, sector, dates, source), recurrence tab | **The existing chart morphs.** Bars and lines move from their old values to the new ones (650 ms). Annotations glide to their new positions. The old chart stays visible during loading, with a thin progress bar | `ChartBox.morph` mutates the existing Chart.js datasets in place and calls `update()`; annotations move with a CSS `transform` transition |
| Hover | The other series dim to 25% over 180 ms; tooltips glide (160 ms) | A small Chart.js plugin draws non-hovered series with lower opacity |
| Counters | Overview numbers count up (900 ms, ease-out) | `requestAnimationFrame` |
| Walkthrough | Spotlight and bubble cross-fade between steps | Vue `<Transition>`, opacity only |
| Pages | Route changes fade/slide 8 px | Vue `<Transition name="route">` |
| Photo result | Detection box(es) scale in one after another (180 ms apart), the verdict badge pops, the facts rise in sequence | CSS keyframes on transform + opacity |
| **prefers-reduced-motion** | **Everything above becomes instant and static**: Chart.js animation off, tooltip animation off, hover dims instantly, counters jump to the final value, walkthrough doesn't auto-advance, every CSS animation/transition duration *and delay* collapses to ~0 | `reduced()` checked at every chart creation and update; one CSS media block |

**Performance budget.**
- **CSS:** every keyframe and transition in `style.css` animates only `transform` or `opacity`. A test enforces this. To pass it, I removed five color transitions from the earlier UI (inputs, buttons, segmented control, drop zone) and one I had added myself.
- **Charts:** they animate on the canvas (Chart.js native).
- **Annotations:** they move with `transform` only.
- **Two honest exceptions:**
  - the count-up counters change text content each frame;
  - the hover dim redraws the canvas for 180 ms.
  Neither causes layout reflow; both are small.
- **Not measured:** frame rate on a real device (see Part 8).

---

## Part 4: visual design

- **UI identity (unchanged tokens):** warm paper background, leaf-green primary, cashew-amber accent; rounded 18 px cards, soft layered shadows, generous padding, subtle vertical gradients behind chart areas; system font stack, so it works offline at the summit.
- **Chart color system: Okabe-Ito** (designed to be distinguishable with color blindness). I ran each set through a palette validator:

| Use | Colors | Validator result |
|---|---|---|
| Good vs rotten | `#009E73` / `#D55E00` | PASS all checks (CVD ΔE 11.0, contrast ≥ 3:1) |
| Growth up vs down | `#0072B2` / `#E69F00` | PASS separation (CVD ΔE 29.2); orange is 2.19:1 on white → relieved by bar direction, arrows and callouts |
| Defect types | `#D55E00`, `#E69F00`, `#CC79A7`, `#0072B2`, `#56B4E9` | PASS separation (worst CVD ΔE 9.6); three colors below 3:1 → relieved by the legend, callout and tooltips |

  Callout text uses darker shades of these hues so text stays readable. All UI text and background pairs were measured at ≥ 4.5:1 earlier, and those tokens are unchanged.
- **Layout:**
  - **Mobile first:** one column.
  - **≥ 640 px:** Gaussian histogram and Q-Q side by side; overview in two columns.
  - **≥ 960 px:** two-column card grid; wide cards span both; forecast small multiples auto-fit.
- **Narrow screens:** fewer x-axis ticks below 520 px. At 360 px the test measured no horizontal overflow and all 17 charts rendered within the viewport.
- **Dark theme:** not added. It wasn't required, and it would have needed a second validated chart palette.

---

## Part 5: the code, file by file and chart by chart

### [frontend/src/series.js](frontend/src/series.js) (new): the numbers each chart draws
These are pure functions with no imports. They turn an API payload into exactly the arrays a chart receives, which is why they can be tested in plain Node against known truths.

- **[`deformitySeries`](frontend/src/series.js#L16):** each type's share per week (null for weeks with no rotten fruit); a `dominant` mask (true where that type has the week's maximum count, so all tied types in a tie); the list of empty weeks; the latest non-empty week.
- **[`forecastSeries`](frontend/src/series.js#L31):** appends the target period to the labels.
  - **Lines:** the history line ends with null, and the forecast line has values only at the last observed point and the target. The fan's upper and lower lines start at the last observed value and open to `[lo, hi]` at the target.
  - **Insufficient data:** all of these are null.
- **[`fruitSeries`](frontend/src/series.js#L61):** values, shares, a `winners` mask (several when tied), and `tie`.
- **[`growthSeries`](frontend/src/series.js#L75):** count and proportion growth, the per-period n, the `na` indices (exactly where growth is null), the sign of each bar, and the last defined value.
- **[`growthRange`](frontend/src/series.js#L89):** one symmetric y-range shared by the good and rotten charts, so they can be compared honestly. The calmer series will look flatter, because it is flatter.
- **[`recurringSeries`](frontend/src/series.js#L95):** buckets, medians and n for the chosen view, plus the peak index of each series.
- **[`gaussianSeries`](frontend/src/series.js#L111):** histogram bins as `{x: centre, y: density, width, count}`, the fitted curve, the ±1σ and ±2σ intervals, the x-range (which can extend past 0% or 100%), and Q-Q points with the reference line.
- **[`overviewSeries`](frontend/src/series.js#L129):** totals per period, the rotten rate per period (null if a period is empty), and sectors sorted by rotten rate.

### [frontend/src/charts.js](frontend/src/charts.js) (rewritten): how each chart looks and explains itself
Shared pieces:
- **`C`:** the Okabe-Ito colors.
- **`reduced()`:** reads `prefers-reduced-motion`.
- **[`stagger()`](frontend/src/charts.js#L41):** spaces out charts that appear together by 110 ms.
- **[`marks`](frontend/src/charts.js#L48):** a Chart.js plugin that draws shaded vertical bands (±σ, impossible zones) and reference lines (50%, mean, average) behind the data.
- **[`dim`](frontend/src/charts.js#L78):** a plugin that lowers the opacity of non-hovered series.
- **`hatch()`:** a diagonal-stripe fill for uncertain or impossible regions.
- **`fade()`:** a vertical gradient fill.
- **[`elRect()`](frontend/src/charts.js#L138):** the final on-screen box of any bar or point. Annotations and the walkthrough use it.
- **`legendFull`:** legend swatches in full color even when the bars are dimmed.

Each `…Spec` function returns `{ config, overlays(chart), finding, steps }`:
- `config` is the Chart.js configuration;
- `overlays` lists the annotations positioned from the chart's geometry;
- `finding` is the one-sentence key finding used as the aria-label;
- `steps` drives the walkthrough.

The charts, in order:
1. **[`deformitySpec`](frontend/src/charts.js#L162): "Qual defeito domina cada semana?"**
   - **Chart:** stacked bars of shares; the dominant segment of each week is drawn full color, the others at 28% opacity.
   - **Annotations:** a callout on the latest week's dominant segment; "n/d" markers on weeks with no rotten fruit.
   - **Tooltip:** share, count, and n of rotten fruit for the week.
2. **[`forecastSpec`](frontend/src/charts.js#L218): "Algum setor vai mandar mais podres que boas?"** One small chart per sector.
   - **Lines:** the solid line is the history (the last 12 periods, labelled "últimos 12 períodos"; the model itself still uses all of them). The dashed line leads to the forecast point.
   - **Fan:** shaded between the 95% limits, with caps at the target.
   - **Annotations:** a dashed 50% line labelled "50%"; a callout with the trend arrow, the forecast % and "chance de + podres".
   - **Unreliable forecast:** a hatched fan, an amber callout, and a "Não confiável" badge whose tooltip gives the reasons.
   - **Insufficient data:** the few real points are still drawn, faded, under a designed "Dados insuficientes: 5 de 8 períodos mínimos" panel.
3. **[`fruitsSpec`](frontend/src/charts.js#L276): "Qual fruta chega em maior quantidade?"**
   - **Chart:** ranked horizontal bars; the winner in full blue, the others pale.
   - **Labels:** count and share at each bar end; the winner's label is a callout with "mais recebida" (or "empate").
4. and 5. **[`growthSpec`](frontend/src/charts.js#L308): "As frutas boas / podres estão aumentando?"** Both cards are identical except for the data.
   - **Chart:** bars for count growth, blue upward or orange downward, with a thin dashed line for proportion growth.
   - **Shared scale:** both cards use the same symmetric y-range.
   - **Annotations:** an "n/d" marker at every undefined period; a callout with the arrow and the change on the last period.
6. **[`recurringSpec`](frontend/src/charts.js#L370): "Em que época do ano o crescimento se concentra?"**
   - **Chart:** grouped bars for good and rotten median growth; each series' peak bar in full color, the rest at 35%; peak callouts.
   - **Switching views:** the week, month and season selector morphs the same chart. Bars move, appear or leave instead of the chart being replaced.
7. **[`gaussianSpecs`](frontend/src/charts.js#L413): "A % de podres de cada setor segue uma curva normal?"** Two charts per sector.
   - **Histogram chart:**
     - **Layers:** real periods as bars, the fitted bell curve on top, ±2σ (light) and ±1σ (darker) bands behind, and the mean as a dark line with a "média" callout.
     - **Out-of-range:** a hatched "impossível" zone where the curve passes 0% or 100%.
   - **Q-Q companion:** points plus the "reta = normal perfeita" line.
   - **Poor fit:** the curve turns grey and dashed, points turn vermillion, both charts get an **AJUSTE RUIM** stamp with the Shapiro p, and the sector box turns amber.
8. **[`overviewSpecs`](frontend/src/charts.js#L498): "Como está a inspeção no geral?"** Three small multiples, each with an animated counter:
   - volume per period (stacked good/rotten) with the total;
   - rotten rate per period (gradient area) with the overall rate and a dashed average line;
   - rotten rate by sector (the highest emphasized) with the number of sectors.

### [frontend/src/components/ChartBox.vue](frontend/src/components/ChartBox.vue) (rewritten)
- **Lazy creation:** an `IntersectionObserver` waits until the chart is near the viewport, then `stagger()`.
- **[`prepare`](frontend/src/components/ChartBox.vue#L45):** injects the motion settings. Entry animation with per-point delay the first time, a 650 ms morph afterwards, and `false` for both when reduced motion is on. It also adds the hover-dim and resize hooks.
- **[`morph`](frontend/src/components/ChartBox.vue#L135):** copies the new data into the *existing* dataset objects, because Chart.js only animates between states when the dataset objects are the same. Then it calls `chart.update()`. This is why filter changes morph instead of re-rendering.
- **[`schedule`](frontend/src/components/ChartBox.vue#L101):** after each render, it computes the annotations from the chart's final geometry and renders them as HTML positioned with `transform`. On first render they fade in once the chart has drawn.
- **[`countTo`](frontend/src/components/ChartBox.vue#L86) and [`dimTo`](frontend/src/components/ChartBox.vue#L62):** the counters and the hover dim.
- **Template:** the frame (focusable, `role="img"`, aria-label = caption + finding), the optional caption and badges, the canvas, the annotation layer, and the designed empty-state panel.

### [frontend/src/components/StatCard.vue](frontend/src/components/StatCard.vue) (rewritten)
- **Header:** the question title, the one-line subtitle, and the "Como ler" button.
- **Badges:** n, demo, and the per-card honesty badges.
- **Loading:** a skeleton shaped like the chart that's coming (`bars`, `hbars`, `hist`, `multiples`). Its shimmer moves with `transform`.
- **Empty states:** designed panels for no data, insufficient data and errors, drawn over faint grid lines.
- **Walkthrough hookup:** it hands its charts to the walkthrough through `provide("registerChart")`.

### [frontend/src/components/Walkthrough.vue](frontend/src/components/Walkthrough.vue) (new)
- **[`resolve`](frontend/src/components/Walkthrough.vue#L36):** turns a step target into a box on the card. A target can be the legend, an axis, a bar or point, a value line, a σ band, the fan, or any element of the card such as the n badge.
- **Display:** a spotlight (the rest of the card dimmed) and a bubble with "Passo i de n" and progress dots.
- **Controls:** auto-advance every 2.8 s, which is off under reduced motion and stops when you interact; ← → keys, Esc, buttons; focus returns to "Como ler" on close.

### [frontend/src/views/DashboardView.vue](frontend/src/views/DashboardView.vue) (rewritten)
- **Loading:** [`load`](frontend/src/views/DashboardView.vue#L35) keeps the previous results visible while new ones load, and sets `refreshing`. That's what lets charts morph instead of being unmounted. Stale responses are dropped.
- **Per-card computeds** (lines 52–133): build the series, the spec and the honesty badges for each card.
- **Filters:** unchanged (period, sector, dates, source).

### Other changed files
- **[frontend/src/strings.js](frontend/src/strings.js):** all new pt-BR text: questions, subtitles, walkthrough steps, badges, empty states, annotation labels and tooltip templates. No pt-BR text is hard-coded elsewhere (checked by a script).
- **[frontend/src/style.css](frontend/src/style.css):** the dashboard section was rewritten: cards, badges, chart frames, annotations, skeleton shapes, empty states, walkthrough, route and photo animations, breakpoints, and the stronger reduced-motion rule (it now also zeroes delays). Five old color transitions were removed for the motion budget.
- **[frontend/src/App.vue](frontend/src/App.vue):** route transition (3 lines).
- **[frontend/src/views/UploadView.vue](frontend/src/views/UploadView.vue):** detection boxes and tags rendered for each detection with staggered delays; verdict gets the `pop` class; color import renamed. The upload logic is unchanged.
- **[core/stats.py](core/stats.py):** two **additive payload fields** for tooltips and the overview chart; the analytics math is unchanged:
  - `history_n` (fruits per period, for each forecast sector);
  - `sectors` (rotten rate per sector) in the overview.

---

## Part 6: honesty in the visuals

- **Small samples look uncertain:**
  - **forecasts:** an unreliable one gets a hatched fan, an amber callout and a "Não confiável" badge;
  - **Gaussian fits:** a grey dashed curve plus the AJUSTE RUIM stamp, or "Amostra pequena" when fewer than 20 periods;
  - **other cards:** "Amostra pequena" when the latest week has < 30 rotten fruits (deformity), the filtered period has < 30 fruits (fruits, overview), there are < 8 complete periods (growth), or each recurrence bar rests on ≤ 1 period.
- **The fan is never made narrower or wider than the model says.** It is the real 95% prediction interval from the backend. Small samples get wider fans because the interval really is wider.
- **No fake zeros:** undefined growth is an "n/d" marker; empty weeks are "n/d"; missing proportions break the line instead of dropping to 0.
- **No empty charts:** no data, too few periods for a forecast, or too few periods for a histogram each show a designed panel inside the chart area.
- **Synthetic data is always labelled:** a page badge plus a "Dados de demonstração" badge on every card.
- **The forecast chart shows only the last 12 periods** so the fan is visible, and says so on the chart ("últimos 12 períodos"). The model is fitted on all periods, so the visible stretch can look flatter or steeper than the fitted trend.
- **Defect types:** the real model only outputs "podre". With real data the deformity chart shows a single color and a "1 tipo de defeito" badge. The three types in the demo exist only in synthetic data.

---

## Part 7: verification

**Commands** (PowerShell, project folder):
```powershell
cd frontend; npm run build; cd ..
$env:DJANGO_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(50))"); $env:DJANGO_HTTPS = "0"
python manage.py test core -v 2
```
- **Browser tests:** need the built frontend, the Python `playwright` package (now in `requirements.txt`) and Microsoft Edge (already installed on Windows).
- **Node tests:** the chart-data checks run inside the Django suite, which generates their fixtures. They can also be run with `cd frontend; node --test tests/series.test.mjs`, but without fixtures only the CSS check runs.
- **Output:** the full run is saved in [dashboard_test_output.txt](dashboard_test_output.txt).

**Result: 38 tests passed:** the 27 earlier backend tests, plus 1 chart-data test (which runs the 10 Node checks), plus 10 browser tests.

### 7.1 The data passed to each chart equals the known truth ([frontend/tests/series.test.mjs](frontend/tests/series.test.mjs), fixtures from [core/test_dashboard.py](core/test_dashboard.py))
How it works: synthetic events with a known answer go into the database, the real API produces the payload, and `series.js` produces what the chart receives.

| # | Ground truth | Measured on the chart data |
|---|---|---|
| 1 | Dominant defect per week (60%), one empty week, one 3-way tie | Highlighted segment = true dominant in 18/18 weeks; max \|share − 0.6\| = 0.053; empty week has no segments; tie highlights all three; stacked shares sum to 1 |
| 2 | Rotten share 0.20 + 0.019/week, next = 0.77; one sector with only 5 weeks | Forecast point 0.7691; fan [0.7341, 0.8040] contains 0.77; fan starts at the last observed point; max \|history − true line\| = 0.030; n per period = 1000; short sector: no fan (all null) |
| 3 | 2500 / 900 / 400 fruits; a tie case | Bars exactly [2500, 900, 400]; winner caju; tie case highlights both tied fruits |
| 4 | Good +10% per month | Max \|bar − 0.10\| = 1.3e-4; n/d at the first period only |
| 5 | Rotten +20% per month | Max \|bar − 0.20\| = 3.9e-4; same shared ±20% range |
| 4/5 | previous = 0 (Jan 100/0, Feb empty, Mar 50/20, Apr 60/30) | n/d exactly at good [0, 2] and rotten [0, 1, 2]; Feb good bar = −100%; Apr rotten = +50% |
| 6 | Known 3-year monthly pattern | Month peaks: rotten = Sep (+30.18%), good = Jan; season peaks: good = summer (+45.6%), rotten = winter (+73.0%), all exact |
| 7 | Sector A μ = 0.20, B μ = 0.35, C skewed | Means 0.2030 / 0.3465; std within 15% of expected; σ bands = mean ± std exactly; histogram area = 1; bin counts sum to n; C flagged (`not_normal`, `outside_01`), curve starts at −19.7% so the impossible zone is drawn |
| 8 | Sector A 10% rotten, B 30%, 2000 fruits per month | Rate 0.2 every month; sectors sorted [B 0.3, A 0.1]; total 6000 |
| CSS | — | 8 keyframes and 8 transitions all animate only transform or opacity |

### 7.2 In the browser (headless Edge against a live test server)
| Test | Measured |
|---|---|
| Every statistic is only charts | All 8 cards have charts (1 + 3 + 1 + 1 + 1 + 1 + 6 + 3 canvases); 0 tables or lists; exactly 1 text paragraph each (the subtitle); every chart frame focusable with an aria-label stating the finding; annotations present on all 8; n badge and "Como ler" on all 8 |
| Lazy render | Gaussian charts created before scrolling = 0, after scrolling = 6 |
| Empty database | All 8 cards show the designed "Sem dados" panel, 0 canvases |
| previous = 0 | Growth cards show `n/d` × 2 (good) and × 3 (rotten), no zero bars |
| Forecast below minimum | The "short" sector chart keeps its canvas, shows "Dados insuficientes: 5 de 8 períodos mínimos (com ≥ 30 frutas cada)" and the "Não confiável" badge; other sectors have no empty state |
| Single sector | Filtering to one sector leaves 1 forecast chart and 1 Gaussian block |
| Failed normality | Skewed sector C flagged, with the AJUSTE RUIM stamp on both charts and the "Ajuste ruim" badge; A and B unflagged, no stamps |
| Reduced motion | **No preference:** chart pixels changed between creation and +1.8 s (animating), card animation 0.5 s, annotation delay 0.7 s. **Reduce:** pixels identical (no animation), card animation 1e-05 s, annotation delay 0 s |
| Filter change morphs | After switching week → month, the **same canvas element** remains (not recreated), it was still animating right after the switch, and the aria-label updated to the new finding |
| Walkthrough | Opens at "Passo 1 de 4" with a spotlight; auto-advances to step 2 after 3.3 s (stays on 1 under reduced motion); arrow keys reach step 4; Esc closes and focus returns to the button |
| Badges | With demo data: page badge plus "Dados de demonstração" on all 8 cards; small-sample/unreliable/poor-fit badges on deformity (1), forecast (3), recurrence (1), Gaussian (3) |
| 360 px | 0 px horizontal overflow; rightmost chart edge 323 px; 17 charts rendered; no JS errors |

### 7.3 Bugs the tests and the visual review caught (all fixed)
- **Walkthrough keyboard:** after a step changed, the focused bubble was replaced, focus fell to the page, and the arrow keys and Esc stopped working. Keys are now handled at window level on a persistent focused element.
- **Walkthrough lag:** the bubble used an `out-in` transition, so the previous step stayed on screen ~220 ms after each key press. It's now a simultaneous cross-fade.
- **Duplicated aria-label:** small-multiple charts said the sector twice ("hills: hills: …").
- **Color transitions:** five color transitions from the earlier UI violated the transform/opacity budget.
- **Visual review:**
  - legend swatches showed the dimmed color;
  - the forecast fan was too thin to see with 104 periods;
  - the overview counters overlapped the plots;
  - two annotation collisions on narrow screens.
- **Test-harness limit (not an app bug):** Django's multi-threaded live test server shares one in-memory SQLite connection, and the dashboard's 7 parallel requests collided on it. The browser tests now use a serial test server. The real app uses a file database with one connection per thread, and handled parallel requests correctly in the earlier end-to-end run.

### 7.4 Bundle size (production build, same measurement before and after)
| File | Before | After | Change |
|---|---|---|---|
| JS (raw) | 311,521 B | 348,862 B | +37,341 B (+12.0%) |
| JS (gzip -9) | 109,871 B | 122,071 B | +12,200 B (+11.1%) |
| JS (brotli) | 96,100 B | 106,816 B | +10,716 B |
| CSS (raw) | 12,224 B | 19,394 B | +7,170 B |
| CSS (gzip -9) | 3,453 B | 5,046 B | +1,593 B |

No animation or chart library was added. The growth is the new chart code, the walkthrough, the annotation layer and the strings. Vite reports gzip as 111.08 kB before and 123.44 kB after; it uses a different compression level. The raw files are in `bundle_before.txt` and `bundle_after.txt`.

---

## Part 8: what was NOT verified

- **Real browsers:** only headless Microsoft Edge (Chromium) on Windows. Not tested: Safari/iOS, Chrome/Android, Firefox, or any visible (non-headless) browser window.
- **Real phones:** 360 px and 390 px were emulated viewports, not devices. Touch, the tap tooltips, and the walkthrough on touch screens were not tried.
- **Frame rate:** the 60 fps target was **not measured** on any device. The only evidence for the budget is the static check that CSS animates only transform/opacity, plus the design of the chart animations. Chart.js redraws the canvas on every animation frame; on a slow phone, 6 Gaussian charts animating together might drop frames. That's untested.
- **Colors on real screens:** checked with a palette validator and contrast math, not on calibrated or real displays, and not with people who have color-vision deficiencies.
- **Screen readers:** the aria-labels and focus order were checked in the DOM. NVDA, JAWS, VoiceOver and TalkBack were not run.
- **Real data:** every statistic was verified only against synthetic data with known answers. Nothing here says anything about real sectors, real seasons or real fruit. With little real data, expect "Dados insuficientes", "Não confiável" and "Amostra pequena" almost everywhere. That's the correct outcome.
- **The upload screen's new animation** (boxes appearing one by one, verdict pop) was not covered by a test.

---

## Part 9: files changed

**Modified:**
- `frontend/src/charts.js` (rewritten)
- `frontend/src/components/ChartBox.vue` (rewritten)
- `frontend/src/components/StatCard.vue` (rewritten)
- `frontend/src/views/DashboardView.vue` (rewritten)
- `frontend/src/strings.js` (dashboard section replaced; new badges/empty/tour sections)
- `frontend/src/style.css` (dashboard section rewritten; 5 color transitions removed)
- `frontend/src/App.vue` (route transition)
- `frontend/src/views/UploadView.vue` (result animation, color import)
- `core/stats.py` (2 additive payload fields)
- `requirements.txt` (`playwright`, test-only)

**New:**
- `frontend/src/series.js`
- `frontend/src/components/Walkthrough.vue`
- `frontend/tests/series.test.mjs`
- `core/test_dashboard.py`
- `DASHBOARD.md`
- `dashboard_test_output.txt`
- `bundle_before.txt`, `bundle_after.txt`

**Not touched:** the model, `infer.py`, `train.py`, `fruit_analytics.py`, authentication, the upload and validation logic, and the backend analytics calculations.
