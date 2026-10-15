# Performance report: control-room upgrade

**Budget stated before the work** ([control_plan.md](../../plans/control_room.md) §4): the existing per-page transfer budgets stay the limit. The new History page gets its own budget. The upload screen must stay light on mobile data.

**Sources of every number:**
- **Page weights:** the test suite (`test_360px_layout_and_page_weight_budgets`).
- **Timing metrics:** [scripts/perf_report.py](../../../scripts/perf_report.py), raw runs in [perf_after.json](perf_after.json).
- **Bundles:** `npm run build`, outputs in [before/bundle.txt](before/bundle.txt) and [after/bundle.txt](after/bundle.txt).

---

## 1. Lighthouse-equivalent lab run (after)

Lighthouse itself was not run. This is the same kind of lab measurement, done with Playwright in headless Microsoft Edge:
- **Device:** mobile emulation, 360×780 at 2× pixel density, touch.
- **CPU:** throttled 4×.
- **Network:** latency 150 ms, 1.6 Mbit/s down, 750 kbit/s up (Lighthouse's "slow 4G").
- **Cache:** disabled.
- **Session:** logged in.
- **Runs:** 3 per page; the table shows the median.

| Page | FCP | LCP | CLS | TBT | Long tasks | Transferred |
|---|---|---|---|---|---|---|
| `/inspecao` (upload screen) | 1,028 ms | 2,288 ms | **0.000** | 387 ms | 2 | 190.3 KB in 24 requests |
| `/painel?source=demo` (dashboard with charts) | 1,068 ms | 2,240 ms | **0.070** | 740 ms | 5 | 228.2 KB in 24 requests |

**How each page's transfer splits (first run):**

| Page | JS | CSS | Font | Images | API | HTML |
|---|---|---|---|---|---|---|
| `/inspecao` | 70.4 KB | 13.1 KB | 12.4 KB | 86.9 KB | 0.6 KB | 2.6 KB |
| `/painel` | 132.5 KB | 13.1 KB | 12.4 KB | 25.0 KB | 38.3 KB | 2.6 KB |

The weights here are at 2× pixel density, so images are larger than in the 1× budget test below.

**Against Google's "good" thresholds:**

| Metric | Good threshold | Result |
|---|---|---|
| LCP | ≤ 2.5 s | Both pages pass, on throttled hardware |
| CLS | ≤ 0.1 | Both pass |
| TBT | lab stand-in for responsiveness (INP) | 387 ms on the upload screen. 740 ms on the Painel, which mostly comes from Chart.js drawing 8 charts on a CPU slowed 4×. Not measured on a real phone |

**Fixed during this measurement: layout shift.**
- **First measurement:** CLS was **0.485** on both pages.
- **Cause, found by attributing the shifts to elements:** the footer was rendered right under the top bar while the page's code was still loading, then jumped down when the page appeared. This was a problem in the app shell before this work.
- **Fix:** `main { min-height: calc(100vh - var(--topbar-h)) }` keeps the footer below the fold until the page renders.
- **Result:** CLS 0.000 on `/inspecao` and 0.070 on `/painel`. The 0.07 that remains is the Painel's "Dados de demonstração" badge wrapping onto a second row at 360 px when demo data arrives.

---

## 2. Page weight per route, before and after (cold cache, 1× density, Brotli)

**Before:** baseline run [before/test_output.txt](before/test_output.txt). **After:** [after/test_output.txt](after/test_output.txt).

| Route | Budget | Before, 360 px | After, 360 px | Before, 1366 px | After, 1366 px |
|---|---|---|---|---|---|
| `/login` | 900 KB | 730.5 | 737.8 | 730.5 | 737.8 |
| `/` (Linha) | 550 KB | 461.0 | 468.5 | 461.0 | 468.5 |
| `/inspecao` | 190 KB | 149.9 | 164.2 | 170.8 | 185.1 |
| `/painel` | 210 KB | 186.1 | 195.8 | 186.1 | 195.8 |
| `/historico` (new) | 200 KB | — | 181.0 | — | 181.0 |
| `/como-funciona` | 450 KB | 254.3 | 155.3 | 362.3 | 338.0 |
| `/como-funciona` scrolled, with the video playing | 2300 KB | 1798.6 | 1810.0 | 1870.9 | 1882.3 |
| `/creditos` | 125 KB | 116.1 | 123.6 | 116.1 | 123.6 |

**One number not explained:** `/como-funciona` at 360 px came out lighter after (155.3 KB) than before (254.3 KB). It is measured, but its cause was not investigated. Below-the-fold images on that page load lazily, so the weight depends on what was in view when the measurement settled.

**What keeps the upload screen light:**
- **Lazy-loaded features:** the inspector, what-if panel, confidence ring, command bar, replay and History are separate chunks, downloaded only when first used.
- **The live strip:** added to the upload page's own chunk.

---

## 3. Bundle, before and after

`npm run build`, sizes before compression (gzip in brackets):

| Chunk | Before | After |
|---|---|---|
| `index` (app shell) | 54.10 kB (21.12) | 62.32 kB (23.87) |
| `strings` (all pt-BR text) | 92.41 kB (35.93) | 101.00 kB (38.90) |
| CSS, every page (`index`) | 53.65 kB (11.92) | 60.75 kB (13.35) |
| New, lazy: CSS for the panels, command bar, what-if, History, ring and pipeline (`control`) | — | 10.47 kB (2.66) |
| `charts` (Chart.js, Painel and Linha only) | 203.82 kB (69.87) | 204.00 kB (69.85) |
| `UploadView` | 11.11 kB (3.96) | 14.52 kB (5.21) |
| `DashboardView` | 27.08 kB (8.61) | 30.92 kB (10.00) |
| `LineView` | 13.43 kB (5.12) | 14.32 kB (5.44) |
| `media` | 14.70 kB (4.67) | 17.53 kB (5.47) |
| New, lazy: `FruitInspector` | — | 8.46 kB (3.46) |
| New, lazy: `HistoryView` | — | 10.05 kB (3.77) |
| New, lazy: `LotReplay` | — | 4.95 kB (2.38) |
| New, lazy: `WhatIf` | — | 4.51 kB (2.06) |
| New, lazy: `CommandBar` | — | 4.31 kB (1.97) |
| New, lazy: `ConfidenceRing` | — | 2.45 kB (1.02) |
| **All precompressed text files** | 2,142,164 B → **740,877 B Brotli** (20 files) | 2,227,707 B → **767,238 B Brotli** (28 files) |

**Total cost:** +26.4 KB Brotli for everything new. No library or font was added. The system monospace stack is used for numbers.

**Why there is a second CSS file.**
- **The failure:** the first full test run failed the Créditos budget by **40 bytes** (125.04 KB against 125 KB). Every page was carrying the styles of the side panel, command bar, what-if, History, ring and pipeline.
- **The fix:** those rules moved to `frontend/src/control.css`, which only those lazily loaded components import, so Vite ships it as its own chunk.
- **Tests still apply:** the CSS tests (token-only spacing, breakpoints, transform/opacity motion) read both files.

---

## 4. Media on disk (`frontend/dist`, without the .br/.gz copies)

| Folder | Before | After | Change |
|---|---|---|---|
| `media/` (photos, posters, videos) | 7,574.5 KB, 112 files | 9,043.3 KB, 124 files | **+1,468.8 KB**: the new "primeira análise" clip |
| `figures/` | 4,469.9 KB, 17 files | 4,469.9 KB, 17 files | unchanged |
| `brand/` | 430.2 KB, 17 files | 430.2 KB, 17 files | unchanged |

**The new clip's files:**
- WebM 609 KB and MP4 490 KB;
- the VTT captions;
- the poster in AVIF/WebP/JPEG at 480/960/1280 px.

**What a visitor downloads of it:** one poster (about 39–54 KB) and one video format. Only if they open History with no real analyses, and only when the video scrolls near. Under reduced motion or Save-Data they get only the poster.

---

## 5. Not measured

- **Real devices:** a real phone, a real network, or Firefox/Safari.
- **Responsiveness in the field:** INP needs real users.
- **"Before" timing:** LCP, CLS and TBT were not measured before the change. Only the before page weights and bundle sizes exist.
- **Frame rate:** no 60 fps measurement on any device.
