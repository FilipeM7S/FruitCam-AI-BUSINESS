# Control room plan (written before implementation)

Spec: "control room" visual, motion and media upgrade. The user chose to execute all of it, in phases. This file is Step 0: what exists today, the data each feature can stand on, every change and file to touch, and what is left for the future.

---

## 1. Step 0 inventory

### Routes ([frontend/src/router.js](../../frontend/src/router.js))

| Route | View | Access | Content |
|---|---|---|---|
| `/login` | LoginView | public | login card, hero photo |
| `/` | LineView | login | hero (simulated-belt background video); line monitor: camera, period and data source; latest frame; KPIs; flow chart; p-chart with alarms; lots table; camera explainer |
| `/inspecao` | UploadView | login | banner; form (sector, fruit card, drop zone, camera); result panel: photo guide → scan line → annotated photo, verdict, probabilities, facts |
| `/painel` | DashboardView | login | sticky filters; 8 statistics in 5 sections; PDF certificate |
| `/como-funciona` | HowItWorksView | public | banner; 7-step pipeline animation (WAAPI); 6 figures; measured model quality; "not evaluated" list; demo video |
| `/creditos` | CreditsView | public | licences: photos, typography, datasets, own material |

### Front end

- **Layout components:** App.vue shell (skip link, top bar, `nav` as bottom bar / rail / sidebar, main, footer, GuideDialog), StatCard, ChartBox, Walkthrough, BrandLogo, ResponsiveImage, LoopVideo, BackgroundVideo, CameraDiagram, PipelineAnimation, GuideDialog.
- **Theme and tokens:** one global [style.css](../../frontend/src/style.css) (3,737 lines), tokens in `:root`, dark only (`meta color-scheme dark`). The previous redesign appended a multicolour theme layer at the end: area accents, colour-cycled numbered sections, gradients.
  - **102 raw colour literals remain outside the token block.** [charts.js](../../frontend/src/charts.js) has its own colour constants.
- **Charts:** Chart.js 4.5.1, one library. Okabe-Ito-based palette in `C`.
- **Animation today:**
  - CSS keyframes and transitions, transform/opacity only. This is enforced by a Node test.
  - WAAPI in PipelineAnimation and the counters.
  - In ChartBox: staggered draw-in, hover dimming of other series, morphing on filter change, shaped skeletons per chart type.
  - `v-reveal` scroll reveals.
  - Reduced motion is fully static (OS setting only; there is no in-app toggle).
- **Bundle:** 53 modules. 20 precompressed files: 2,142,094 B raw → 740,840 B Brotli.
  - Largest chunks: charts 203.8 KB (69.9 KB gzip, dashboard only), strings 92.4 KB, index 54.1 KB, CSS 53.7 KB (11.9 KB gzip). Full output in [visual/before/bundle.txt](../reports/visual/before/bundle.txt).
- **Media on disk** (`frontend/dist`): media 7,574.5 KB (112 files), figures 4,469.9 KB (17), brand 430.2 KB (17); 12.69 MB in total. A visitor downloads one format and one width.
- **Page weight at 360 px** (transferred, measured by `test_360px_layout_and_page_weight_budgets`), against these budgets:

| Route | Weight | Budget |
|---|---|---|
| `/login` | 716.1 KB | 900 KB |
| `/` | 446.6 KB | 550 KB |
| `/inspecao` | 135.5 KB | 190 KB |
| `/painel` | 171.7 KB | 210 KB |
| `/como-funciona` | 146.0 KB | 450 KB |
| `/creditos` | 101.6 KB | 125 KB |

### Tests and their result

[visual/before/test_output.txt](../reports/visual/before/test_output.txt): `python manage.py test core -v 2`, Ran 103 tests in 9,722.9 s, 102 passed.
- **The 1 failure was real:** `test_logo_is_the_dark_variant_and_blends_with_the_bar`. The redesign had tinted the top bar, so the logo plate showed as a box.
- **Fixed** by removing the tint; the test was re-run and passes.
- **Test files:** `core/tests/test_api.py` (27), `test_belt` (17), `test_certificate` (10), `test_dashboard` (11), `test_datasets` (10), `test_layout` (11), `test_media` (13), `test_showcase` (5, one new for sorting), and `frontend/tests/series.test.mjs`.

### Screenshots before

[visual/before/](../reports/visual/before): every page at 360, 768 and 1280 px, plus the inspection result. Taken by `scripts/layout_screenshots.py`, which uses a throwaway database.

---

## 2. What data exists per fruit (every control feature must stand on this)

**`Event` row:** id, timestamp, sector, fruit_type, is_good, deformity_type, confidence, user, is_demo, image, source (`foto` / `camera`), camera, lot, track_id, label, size_mm, needs_review, decided_by, model_version.

| Fact | Consequence |
|---|---|
| A photo upload stores the full image (PNG, random name, in `UPLOAD_DIR`, never served today) | The inspector can show the stored photo through a new authenticated, owner-only thumbnail endpoint |
| The **box**, the **crop** and the **per-class probabilities** exist only in the `/api/analyze` response, not in the database | The inspector shows box, crop and probabilities only for the result just analysed (crop cut in the browser from the user's own file). For stored events it shows only stored fields |
| The photo endpoint returns **exactly one detection** (one box per photo) | The "tracking trail between several boxes" has no real case → **future** |
| **Lots** exist only for camera events; a camera keeps only its latest `frame.jpg` | Lot replay is for camera lots. There are no per-event camera images |
| Real review rule: `needs_review = reject_below is None or confidence < reject_below`. The current model has `reject_below = null`, so every photo fruit goes to review | What-if shows the real threshold as "nenhum (tudo vai para revisão)" next to the simulated one |
| Today's database: 95,474 camera demo events (12 lots, 2 cameras, all with confidence); 163,488 Painel demo events (now with class and confidence, see docs/guides/showcase.md); 3 real photo events | Everything shown from demo rows keeps the DEMO badge |
| There is no table for overrides, relabels or feedback | No write endpoints are added |

---

## 3. Changes, phase by phase, with every file

### New back-end endpoints

All are read-only, `GET`, `IsAuthenticated` (the existing auth), with validated filters and JSON errors. Tests go in a new `core/tests/test_control.py`.

| Endpoint | Returns | Validation |
|---|---|---|
| `/api/events` | Paged event rows, newest first, with `total`. Filters: source, sector, fruit_type, label, kind (foto/camera), camera, lot, review (yes/no), start, end. `order=asc` and a compact `shape=columns` for lot replay | Whitelisted values, ISO dates, `size` ≤ 500 (≤ 20,000 only with `lot`), 400 `invalid_filter` otherwise |
| `/api/events/<id>` | One event: only stored fields, plus `image_available` | 404 if missing |
| `/api/events/<id>/image` | 320 px JPEG thumbnail of the stored upload | Only the uploader or staff; 404 otherwise; `Cache-Control: private, no-store` |
| `/api/events/thresholds` | Per class, a 100-bin confidence histogram over the filtered events, the count without confidence, and the model's real `reject_below` and version | Same filters as `/api/events` |

The histogram bins use the slider's own thresholds (`j/100`), so "confidence < t" sums are **exact** at every slider step. No stored data or model setting changes.

**Back-end files:** [core/views.py](../../core/views.py) (or a new `core/event_views.py`), [fruitcam/urls.py](../../fruitcam/urls.py), `core/tests/test_control.py`. Not touched: the model, training/infer.py, auth, upload validation, analytics math.

### Phase 1: control-room theme

- **Tokens:** every colour becomes a token in one block, with a dark set (default) and a light set (`[data-theme="light"]`). The 102 raw literals and the chart chrome colours are replaced.
  - **Instrument panels stay dark in both themes:** charts, the photo HUD and the live frame. That way the Okabe-Ito palette keeps the contrast it was designed for, unchanged.
  - **Light theme surfaces:** cream `#f5f1e6`, the light logo plate colour, so the light plate blends into the bar.
- **Restraint:** the multicolour layer (gradients, glows, colour-cycled sections) is replaced by the HUD language:
  - 1 px strokes and corner brackets on cards and the photo;
  - a faint blueprint grid;
  - monospace tabular numbers;
  - one "system active" accent.
  - Area colours remain only as a small index tick.
- **Status chips:** ATIVO, ANALISANDO, SEM DADOS, DEMO, SIMULAÇÃO. Each has a text label and a shape, never colour alone.
- **Theme toggle** in the top bar, saved in `localStorage`. A pre-paint `public/theme.js` (external, because of the CSP) prevents a flash. `meta color-scheme` becomes `dark light`. `BrandLogo` already picks `on-dark` / `on-light` from `theme.dark`.
- **Files:** style.css, index.html, public/theme.js (new), media.js, App.vue, BrandLogo.vue, charts.js, strings.js, core/tests/test_media.py (expected meta).

### Phase 2: control features

- **Command bar (Ctrl/Cmd+K, plus a visible "Ctrl K" button):** pages; filters (sector, period on Painel and History; fruit on History); "lote L1-…" opens the replay; "#123" opens the inspector. Arrow keys, Enter, Esc; focus is trapped and then returned.
  - New `components/CommandBar.vue`. The Painel reads and writes its filters in the URL query.
- **Fruit inspector:** a side panel (dialog) with only the fields that exist (section 2). It opens from the photo result and from History rows. New `components/FruitInspector.vue`.
- **Live-state strip** on Inspeção: PRONTO → ENVIANDO (real XHR upload progress) → ANALISANDO → CONCLUÍDO, with the real `inference_ms` and the measured round trip, or ERRO. An `upload()` helper with XHR goes in api.js.
- **What-if threshold:** `components/WhatIf.vue` on the result and on the Painel. It recomputes counts and shares in the browser from `/api/events/thresholds`.
  - **Labels:** "SIMULAÇÃO · simulação sobre dados salvos", with the real threshold and the simulated one both visible.
  - **Morphing:** the Chart.js chart morphs with `update()`.
- **Lot replay:** `components/LotReplay.vue` on the Linha lots table. A scrubber with play/pause replays the lot's stored events in time order. It shows cumulative counts and the rotten share, and ends at the static totals.
- **History:** new route `/historico`, new `views/HistoryView.vue`.
  - Filters, a paged table, row checkboxes and select-page.
  - **Bulk actions are read-only:** a summary of the selection and a CSV export.
  - Added to the nav and the command bar.
- **Traceability:** a `v-trace` directive (in the new motion/media module) on every metric. Hover or focus shows the source: endpoint, n, period, filter, event count. Chart tooltips get the same footer.
- **Files:** App.vue, router.js, api.js, strings.js, style.css, UploadView.vue, DashboardView.vue, LineView.vue, StatCard.vue, ChartBox.vue, plus the new components above and `src/control.js` (shared state and the trace directive).

### Phase 3: animations

- **Photo:**
  - the scan sweep (exists);
  - corner-bracket reticles that lock onto the box;
  - the verdict chip pop (exists);
  - a confidence ring that fills by `transform: rotate` of two half-masks (transform only);
  - counters that tick to the real values.
- **Painel:**
  - already present: staggered draw-in, hover dimming, morphing and tickers;
  - **new:** a sonar pulse on the ATIVO chip, and a drill-down. Clicking a bar draws an SVG connector from the bar to the inspector or History (filtered to the fruit behind the bar).
- **Page level:**
  - View Transitions API for route changes and a thumbnail → inspector shared element, with the current CSS transition as the fallback;
  - magnetic hover on primary buttons (transform only, pointer: fine only);
  - shaped skeletons (exist).
- **Pipeline:** an SVG camera → detection → classification → event → statistic → report, drawn step by step (stroke-dashoffset is not transform, so each segment is revealed with `scaleX` instead), with replay. It replaces the 7-card list on Como funciona; the text stays.
- **"Reduzir animações":** a toggle that sets `data-motion="reduced"` on `<html>`, saved, and read by every animation and video path through `reducedMotion()`.
- **Files:** style.css, media.js (`reducedMotion` also reads the toggle), PipelineAnimation.vue, UploadView.vue, ChartBox.vue, DashboardView.vue, App.vue, the new `control.js`.

### Phase 4: video and images

- **Existing:** recorded app loops with poster, captions, transcript, keyboard play/pause, reduced-motion and Save-Data fallback (LoopVideo); responsive AVIF/WebP/JPEG photos with alt text and a licence manifest (ResponsiveImage, licenses.json). They are checked and kept.
- **Gaps to fix:**
  - **BackgroundVideo** (Linha hero, login) loops with no pause control. WCAG 2.2.2 requires one, so a keyboard-operable pause button is added.
  - **New Playwright recordings of the real app**, compressed with ffmpeg to WebM + MP4 with poster, captions and transcript, and added to the manifest:
    - "como funciona" (the inspector and what-if);
    - empty state (History with no real data);
    - onboarding (photo guide).
- **Photos:** only those already licensed. The logos are used as supplied. Nothing is drawn or generated.
- **Files:** BackgroundVideo.vue, tools/record_demo.py (new clips), tools/build_media.py and assets/media_src/catalog.json only if new clips are added, licenses.json via the generator.

### Phase 5: verification and docs

- **Tests:** new `core/tests/test_control.py`, extensions to the Node tests, updated budgets only if justified.
- **Screenshots:** `docs/reports/visual/after/`.
- **Performance report:** `docs/reports/visual/perf.md`.
- **Explanation:** `docs/guides/control_and_motion.md`.

---

## 4. Budgets

- **Page weight:** the existing budgets stay the limit. `/inspecao` ≤ 190 KB and `/painel` ≤ 210 KB at 360 px, cold cache.
- **New code is lazy-loaded:** the command bar, inspector, what-if, replay and History load on first use, so the upload screen on mobile data pays only for the live strip and the theme toggle.
- **No new library, no new font:** numbers use the system monospace stack.
- **Performance stand-in for Lighthouse:** Playwright with CDP CPU ×4 and Fast 3G throttling, measuring LCP, CLS, long tasks and transferred bytes for `/inspecao` and `/painel`, before and after.

---

## 5. Future (not built, because the data or the schema does not exist)

- Storing the box, the crop and the per-class probabilities of each photo event, so the inspector can show them for history.
- Multiple detections per photo, and with them the tracking-trail animation.
- Per-event camera crops (today only the latest frame per camera exists).
- Lots for photo events.
- Review, relabel and feedback writes: they need a reviewed-label table with an audit trail, and a review screen.
- Field accuracy: "ainda não avaliado" until measured on held-out real conveyor images.

---

## 6. Deviations found while implementing

The implementation is explained in [control_and_motion.md](../guides/control_and_motion.md).

- **Pipeline:** the 6-step SVG pipeline was **added above** the existing 7-step technical pipeline instead of replacing it. The 7 steps explain details (segmentation, tracking, decision) that the 6-step overview leaves out.
- **Drill-down:** on the two bar charts whose bars map one-to-one to an event filter (fruit type and sector). The other charts (weekly defect mix, growth, forecasts, fits) have no single filter that reproduces a bar exactly, so they get no drill-down.
- **Parameter name:** the compact replay format is `shape=columns`, not `format=columns`. DRF reserves `format`.
- **Endpoint addition:** `shape=lots` was added to `/api/events` for the command bar's lot list.
- **Layout-shift fix:** measuring performance found CLS 0.485 caused by the footer jumping. This was an app-shell problem older than this work. Fixed with `main { min-height }`.
- **Media build:** it deleted its whole output folder first. On this machine Windows refused to delete the OneDrive-synced folder halfway through. Seven tracked videos were deleted and restored from git, and the build now deletes only files.
- **Painel default:** added after the user saw the "Reais" view (3 real events from one day) showing "Dados insuficientes" everywhere. With under 14 days of real history, the Painel now opens on the labelled demo data. The camera lines also got 3 years of synthetic photo-sampling history, so every chart is drawn. Real rows were never touched.
- **CSS split:** styles used only by lazily loaded components moved to `frontend/src/control.css`, after the Créditos page went 40 bytes over its 125 KB budget. The layout and motion tests read both stylesheets.
- **Overflow fix:** the lots table's new, visually hidden "Reprodução" header is `position: absolute`. It was positioned against the panel and escaped the table's scroll box, widening the Linha page to 616 px on phones. `.lots-scroll` is now the positioning context.
- **Missing media:** the onboarding "how to take a good photo" video needs supplied footage. Checklist in [control_and_motion.md §7](../guides/control_and_motion.md#7-video-and-images).

