# Control room, motion and media: how it works

This document explains the "control room" upgrade of the FruitCam_ai web app. It starts with plain concepts and goes down to the code, file by file. The code has no comments, so this file is the only explanation.

> **Update, 2026-10-11 (continuous operation).** The camera worker was rebuilt to run without pauses: a reader thread that keeps only the newest frame, an on-disk queue so no counted fruit is lost, exactly-once storage, per-minute and per-day aggregates kept as each fruit is stored, a supervisor that restarts a camera that stops, a live event stream for the *Linha* page and a health endpoint. Where this guide describes the worker loop, the 15 s polling or how `/api/line` is cached, it describes the earlier design. The current design, with measurements and tests, is in [architecture/realtime.md](../architecture/realtime.md) (in Portuguese).

> **Update, 2026-10-11 (one place for licences and credits).** Licences, authors and credits now live in one place: [LICENSES.md](../../LICENSES.md), generated from `legal/registry.json` by `tools/build_legal.py`, and shown on the site's *Créditos* page. The pages no longer print a credit line under each photo; the "Imagem ilustrativa" label links to *Créditos*. Where this guide mentions a visible credit line, `licenses.json` or licence details in `SOURCE.md`, it describes the earlier design. How the place works: [legal/README.md](../../legal/README.md).

> **Update, 2026-10-11 (folders).** The project folders were reorganised on this date. The links in this guide were updated; commands quoted inside recorded outputs keep the paths of the day they ran. The current map is in the root [README.md](../../README.md).

The plan written before the work is [control_plan.md](../plans/control_room.md). The performance report is [visual/perf.md](../reports/visual/perf.md).

**Rule behind every feature:** the feeling of control comes from real controls over real data.
- Nothing on screen is a fake live feed, a fake metric or a fake guarantee.
- Synthetic data always carries a **DEMO** badge.
- Anything recomputed in the browser is labelled **SIMULAÇÃO**.

---

## Contents

1. [What changed, in one table](#1-what-changed-in-one-table)
2. [Concepts in plain words](#2-concepts-in-plain-words)
3. [The data the controls stand on](#3-the-data-the-controls-stand-on)
4. [Theme: control-room look, dark and light](#4-theme-control-room-look-dark-and-light)
5. [Control features](#5-control-features)
6. [Motion](#6-motion)
7. [Video and images](#7-video-and-images)
8. [Performance and budgets](#8-performance-and-budgets)
9. [Tests](#9-tests)
10. [Files changed](#10-files-changed)
11. [What was not verified](#11-what-was-not-verified)
12. [Future: not built, because the data does not exist](#12-future-not-built-because-the-data-does-not-exist)

---

## 1. What changed, in one table

| Area | Feature | Where it appears |
|---|---|---|
| Theme | Dark-first theme with a light theme. HUD language: 1 px strokes, corner brackets, a faint grid, monospace numbers, status chips. | Every page; toggle in the top bar |
| Control | Command bar (Ctrl/Cmd+K) | Top bar button and keyboard shortcut |
| Control | Fruit inspector (side panel) | Photo result, History rows, command bar `#id`, drill-down list |
| Control | Live-state strip: PRONTO → ENVIANDO → ANALISANDO → CONCLUÍDO, with real times | Inspeção por foto |
| Control | What-if review threshold, labelled "SIMULAÇÃO · simulação sobre dados salvos" | Photo result, and a new Painel section "Limiar de revisão" |
| Control | Lot replay with a scrubber | Linha (lots table) and command bar |
| Control | History with filters, bulk selection, selection summary and CSV export | New page `/historico` |
| Control | Traceability: hover or focus a number to see its source | KPIs, n badges, chart tooltips, what-if, History total, inspector |
| Control | Drill-down: click a bar to list the fruits behind it, with an animated connector line | Painel: "Qual fruta chega" and "Taxa de podres por setor" |
| Control | When real data covers less than 2 weeks, the Painel opens on demo data, with a visible notice | Painel |
| Motion | Reticles that lock on, a confidence ring, counters that tick to real values | Photo result |
| Motion | Sonar pulse on ATIVO, view transitions, a shared-element thumbnail → inspector, magnetic buttons | App-wide |
| Motion | 6-step SVG pipeline drawn step by step, with replay | Como funciona |
| Motion | "Reduzir animações" toggle | Top bar |
| Media | New recording of the real app ("primeira análise", Playwright `recordVideo`) | History empty state |
| Media | Pause button on background videos | Linha hero, login |
| Server | 4 read-only, authenticated endpoints | `core/event_views.py` |

---

## 2. Concepts in plain words

**Design token.** A named value, such as `--surface: #1a2c25`, defined once and used everywhere instead of the raw value.
- To change a colour, you change one line.
- A theme is just a different set of token values.
- After this work, the stylesheet has **no raw colour outside the token blocks**. The chart colours are read from the same tokens.

**HUD.** "Head-up display": the thin-line, data-first look of an instrument panel.
- Here it means 1 px strokes, corner brackets on cards and photos, numbers in a monospace font with fixed-width digits ("tabular" numbers, so columns don't jitter), and small status chips.
- It is restrained: no neon and no glow.

**Keyframe animation.** A CSS animation described by its start and end states (`@keyframes lock { from {...} to {...} }`). The browser fills in the frames in between.

**WAAPI.** The Web Animations API: `element.animate([...], { duration })` in JavaScript. It does the same as a keyframe, but can be started, paused and cancelled from code. The pipeline uses it to pause when off-screen.

**Transform and opacity only.** The browser can animate `transform` (move, scale, rotate) and `opacity` on the graphics card, without recomputing the page layout. Animating anything else forces layout work on every frame. Every animation here follows this rule, and a Node test enforces it.

**View Transitions API.** `document.startViewTransition(update)`.
- The browser takes a picture of the page, runs `update`, and cross-fades to the new state.
- If an element has the same `view-transition-name` before and after, it flies from its old place to its new one. That is how a History thumbnail "becomes" the photo in the inspector.
- Browsers without the API simply update the page without animation.

**Reduced motion.** People with vestibular disorders can ask the operating system to reduce motion (`prefers-reduced-motion`). The app also has its own "reduzir animações" button. In both cases every animation is replaced by its final state, and every video by its poster image.

**Core Web Vitals.** Google's user-experience measures:
- **LCP (Largest Contentful Paint):** when the main content appeared. Good is ≤ 2.5 s.
- **CLS (Cumulative Layout Shift):** how much the page jumps while loading. Good is ≤ 0.1.
- **INP:** responsiveness to input. It can't be measured without real users. Its lab stand-in is **TBT (Total Blocking Time)**: the time the main thread was blocked by long tasks.

**Modal dialog.** The inspector and the command bar are `<dialog>` elements opened with `showModal()`. The browser makes the rest of the page inert, keeps keyboard focus inside, and closes on Esc. Focus returns to the element that opened it.

**Combobox.** The command bar's input is a WAI-ARIA combobox: the arrow keys move a highlighted option (`aria-activedescendant`) while typing continues in the input.

**What-if simulation, exactly.**
- **The real rule:** a fruit goes to manual review when its confidence is below the model's threshold.
- **The current model has no threshold** (`reject_below = null`), so every photo fruit goes to review.
- **How it is computed:** the server returns, per class, how many saved events fall in each confidence step of 0.01 (101 bins). For a simulated threshold t = j/100, "below t" is the sum of the first j bins.
- **Why it is exact:** each bin uses the same `j/100` numbers as the slider, so the counts are exact at every slider position, not approximated. A test checks all 101 positions against the database.

**Prefix sums (replay).** To replay a lot at position i, the browser needs "how many of each class among the first i fruits". Computing the running totals once (`cum[c][i]`) makes every slider position instant.

---

## 3. The data the controls stand on

Every control uses only fields that exist in the `Event` table:
- id, timestamp, sector, fruit_type, is_good, deformity_type, confidence, user, is_demo, image;
- source (`foto` / `camera`), camera, lot, track_id, label, size_mm, needs_review, decided_by, model_version.

| Stored? | Consequence in the UI |
|---|---|
| Full uploaded photo: yes, but it was never served | The inspector shows it as a 320 px thumbnail, **only to the user who uploaded it** (or staff) |
| Box, crop, per-class probabilities: **no**, they exist only in the analysis response | The inspector shows them only for the photo just analysed. The crop is rebuilt in the browser from your own file. For saved events it says "Só aparecem os campos armazenados" |
| One box per photo | The tracking-trail animation has no real case, so it is listed as future |
| Lots: only camera events | Replay is for camera lots |
| No override/relabel table | No write endpoint was added; every control is read-only |

---

## 4. Theme: control-room look, dark and light

**Files:** [style.css](../../frontend/src/style.css), [index.html](../../frontend/index.html), [public/theme.js](../../frontend/public/theme.js), [media.js](../../frontend/src/media.js), [App.vue](../../frontend/src/App.vue), [charts.js](../../frontend/src/charts.js).

### Tokens in one place

The top of `style.css` now has three blocks:
1. **`:root` (layout):** font stacks (`--font`, `--mono`), spacing scale, widths, bar heights.
2. **`:root, … instruments` (dark colour set):** every colour, including the new ones: `--active` (system-active accent), `--hud-line`, `--bracket`, `--grid-line`, the info and neutral chip colours, the chart chrome (`--chart-ink`, `--chart-grid`, …), skeleton colours, shadows and the camera-diagram colours.
3. **`:root[data-theme="light"]` (light overrides):**
   - cream `#f5f1e6`, the light logo plate colour, so the plate blends into the top bar;
   - darker text tints of the class colours, for AA contrast on light surfaces.

**Replacing raw colours.** A one-off script replaced the 96 raw colours left in the stylesheet with tokens. It refused to finish while any raw colour remained outside the token blocks.

**Chart colours.** `charts.js` reads `--good`, `--rotten`, `--chart-ink` and the others at load time through `token(name)`, so the stylesheet is the single source of truth.

**Data palette.** The class colours (`--good`, `--poor`, `--rotten`, `--review`, `--info`) are the same in both themes, as required ("palette unchanged").

### Instruments stay dark in both themes

Charts, the live camera frame, the photo result, the camera diagram, photo/video banners, the login screen (over its video) and the footer re-declare the dark tokens even in the light theme. In a real control room the screens are dark while the room is lit.
- **Why:** the Okabe-Ito chart palette and the chart text were designed and tested on dark panels, so they keep their contrast without a second palette.
- **How:** one selector list (`:root[data-theme="light"] :is(.chart-frame, .chart-panel, .live, .annotated, .cam-diagram, .page-banner, .login, .site-footer, .instrument)`) on the dark token block.

**Second stylesheet.** Styles used only by lazily loaded components (side panel, command bar box, what-if, History, confidence ring, pipeline) live in [control.css](../../frontend/src/control.css). Those components import it, so it is downloaded only with them. The layout and motion tests read both files.

### HUD details (the theme layer at the end of `style.css`)

- **Corner brackets:** an `::after` layer with eight 1.5 px gradients (two per corner). Cards get faint brackets; photos and the camera frame get bigger white ones. There is no extra markup.
- **Grid:** two repeating 1 px gradients on `.app` (32 px cells, about 4% opacity). The top bar stays the exact plate colour.
- **Numbers:** `.kpi-value`, probabilities, facts, the lots table, n badges and `.num` use `--mono` with `tabular-nums`. The font is the system monospace stack, so no download.
- **Status chips:** `.chip[data-state=…]`: ativo ●, analisando ◐ (spins), enviando ◐, concluido ✓, demo ◆, simulacao ◇, ia ◈, erro ✕, off ○.
  - Every chip has a text label and a shape, so colour never carries the meaning alone.
  - The shapes use `content: "●" / ""` so screen readers skip the glyph.
- **Area colours:** reduced to a small tick under the page title and the navigation icons.
- **Removed from the earlier multicolour layer:** gradients, glows and colour-cycled sections.

### Theme toggle and logo

- **Toggle:** the sun/moon button calls `setTheme()` in `media.js`. It sets `data-theme="light"` on `<html>`, stores the choice in `localStorage`, and updates `<meta name="theme-color">`.
- **No flash on load:** `public/theme.js` applies the saved theme (and the saved motion choice) before the page paints. It is an external file because the Content Security Policy forbids inline scripts.
- **Logo:** `BrandLogo` already picked `on-dark` or `on-light` from `theme.dark`, which is now reactive. The footer is always dark and is forced to `on="dark"`.
- **Tested:** in both themes, the logo's corner pixel equals the bar's background colour.

---

## 5. Control features

### 5.1 Back end: four read-only endpoints ([core/event_views.py](../../core/event_views.py), routes in [fruitcam/urls.py](../../fruitcam/urls.py))

All four are `GET` only and behind the existing session authentication (`IsAuthenticated` is the project default). Invalid input returns `400 {"error": {"code": "invalid_filter"}}`.

| Endpoint | Returns | Validation |
|---|---|---|
| `/api/events` | Event rows, newest first, with `total` and a `demo` flag. `order=asc`, `shape=columns` (compact arrays for replay), `shape=lots` (distinct lots with n, first, last, demo) | source ∈ real/demo/all; kind ∈ foto/camera; label ∈ the 3 classes; review ∈ yes/no; fruit ∈ the 3 fruits; text filters ≤ 50 characters; ISO dates and datetimes; `size` 1–500 (up to 20,000 only with `lot`); `page` ≥ 1 |
| `/api/events/<id>` | One event: only stored fields, plus `image` (true only if you may see the photo) | 404 if missing |
| `/api/events/<id>/image` | 320 px JPEG thumbnail of the stored upload, `Cache-Control: private, no-store` | Only for the uploader or staff. The file name must match `[0-9a-f]{32}.png`, so path tricks return 404 |
| `/api/events/thresholds` | Per class: the 101-bin confidence histogram, n and the stored review count. Also the number of events without a confidence, and the model's real `reject_below` and version | Same filters as the list |

**Parameter name.** DRF reserves the `format` query parameter for its own content negotiation. The first version used it and got 404s, so it is called `shape`.

**The real threshold.** It comes from the loaded model (`get_model()[0].reject_below`). The model is already loaded at server start, so this costs nothing.

### 5.2 Command bar ([components/CommandBar.vue](../../frontend/src/components/CommandBar.vue))

- **Opening:**
  - Ctrl+K, or Cmd+K on Mac, toggles it (handler in `App.vue`).
  - The top-bar button shows the hint "Ctrl K" or "⌘ K" and carries `aria-keyshortcuts`.
  - On phones, the button shows only the search icon.
- **Results:**
  - pages;
  - filters ("Painel · setor X", "Painel · por mês", "Histórico · Castanha", "Histórico · só frutas para revisão");
  - lots, loaded from `/api/events?shape=lots`;
  - display actions (theme, motion);
  - typing `#123` or `123` offers "Abrir registro #123".
- **Search:** ignores accents and case, and every typed word must match.
- **Keyboard:** ↑/↓ move, Enter runs, Esc closes and returns focus.
- **Painel filters in the URL:** the Painel reads and writes its filters in the URL (`/painel?sector=sul&period=month`), so the command bar, the back button and shared links all work.

### 5.3 Fruit inspector ([components/FruitInspector.vue](../../frontend/src/components/FruitInspector.vue), state in [control.js](../../frontend/src/control.js))

`openEvent`, `openEventId`, `openDrill` and `openReplay` set a small reactive `panel` store. `App.vue` lazy-loads the inspector only when the store is set.

| Opened from | What it shows |
|---|---|
| Photo result | Always reloads the stored row from `/api/events/<id>`, so it shows exactly what was saved. Adds the parts that exist only for this fresh result: the **crop** (cut in the browser with the same 15% margin as the server's `fruit_crop`), the per-class probabilities, and the box coordinates |
| History, `#id`, a drill-down row | Only the stored fields that are not empty, and the stored photo if you uploaded it |

**Chips:** RECÉM-ANALISADA or REGISTRO SALVO, DEMO, SIMULAÇÃO (when `decided_by = simulacao`), REVISÃO.

**Source line:** the field list carries the trace "Fonte: registro #id lido do banco (GET /api/events/id)".

### 5.4 Live-state strip ([views/UploadView.vue](../../frontend/src/views/UploadView.vue), `upload()` in [api.js](../../frontend/src/api.js))

- **Why XHR:** `fetch` cannot report upload progress, so the photo is sent with `XMLHttpRequest`. The CSRF retry is the same as in `api()`.
- **The states are the request's real events:**
  - ENVIANDO while `upload.onprogress` reports bytes (shown as a %);
  - ANALISANDO after `upload.onload`;
  - CONCLUÍDO when the response arrives;
  - ERRO on failure.
- **Times shown:**
  - "Inferência X ms (medida no servidor)", the server's own `inference_ms`;
  - "Ida e volta Y s (medida no navegador)", measured with `performance.now()`.
- **Screen readers:** a visually hidden live region announces each state change once, not every percentage.
- **No simulated feed:** nothing in the strip is simulated, so it needs no SIMULAÇÃO label.

### 5.5 What-if threshold ([components/WhatIf.vue](../../frontend/src/components/WhatIf.vue))

- **Labels:** "SIMULAÇÃO" and "Simulação sobre dados salvos. Nada é gravado e o modelo não muda…"
- **Real threshold:** "Limiar real do modelo belt_v2: nenhum (toda fruta vai para revisão)" sits next to the simulated slider value.
- **Table:** per class, the **saved** decided count (`n − stored_review`) and the **simulated** count (`n − Σ bins below t`), plus a "Revisão" row.
- **Morphing:** bars are `transform: scaleX()` with a 0.3 s transition, so they morph as the slider moves. Numbers tick to the new value in 350 ms.
- **On the photo result:** the query is `source=real&kind=foto&mine=1` (your saved photos). A sentence states what would happen to this fruit at the simulated threshold.
- **On the Painel:** the query is the current filters, and the table says how many events have no confidence and stay outside the simulation.

### 5.6 Lot replay ([components/LotReplay.vue](../../frontend/src/components/LotReplay.vue))

- **Data:** loads the lot's stored events in time order (`shape=columns`, `order=asc`). Opened from the Linha table, it uses the same time window as the table (`since`/`until` = the summary's start/end), so the end of the replay **equals the row in the table**. A test checks this.
- **Running totals:** built once (§2).
- **Controls:**
  - the scrubber (`<input type="range">`, with a `aria-valuetext` such as "1.097 de 2.612 frutas · 19:37:55");
  - Reproduzir/Pausar (6 s for the whole lot);
  - Do início.
- **Chart:** an SVG line of the cumulative % of rotten fruit, revealed with a `scale(i/n, 1)` clip. The y-axis is fitted to the data and labelled.
- **Reduced motion:** opens at the final state, and Reproduzir jumps to the end.

### 5.7 History ([views/HistoryView.vue](../../frontend/src/views/HistoryView.vue), route `/historico`)

- **Filters:** source, origin (foto/câmera), sector, fruit, class, review, lot and dates. They are synced to the URL.
- **Table:** paged by 50, with a thumbnail for your own photos.
- **Bulk selection:**
  - row checkboxes and "Selecionar a página";
  - the selection summary gives the count per class and the mean confidence;
  - **Exportar CSV** creates the file in the browser (`;`-separated, UTF-8 with BOM, so Excel opens it).
- **Read-only:** no relabel or delete.
- **Empty state (no real data):** says how to make the first analysis and shows the "primeira análise" recording (§7).

### 5.8 Traceability (`vTrace` in [control.js](../../frontend/src/control.js))

`v-trace="text"` turns any number into a traceable value:
- dotted underline, `tabindex=0`, and a tooltip (`role="tooltip"`) on hover or focus, linked with `aria-describedby`;
- Esc dismisses it, and the pointer can move onto the tooltip without losing it (WCAG 1.4.13).

| Where | Example text |
|---|---|
| Linha KPIs and chart tooltips | "Fonte: GET /api/line · Linha 1 · 1 h · fluxo por janela de 1 min · Demonstração · n = 6.943" |
| Painel n badges and every chart tooltip (footer) | "Fonte: GET /api/stats/fruits · período semana · setor todos · fonte demonstração · n = 24.981" |
| What-if numbers | endpoint, filter and the number of events with a confidence |
| History total, replay counts, inspector fields | endpoint, filter and count, or the record id |

### 5.9 Drill-down ([ChartBox.vue](../../frontend/src/components/ChartBox.vue), `drill` in [charts.js](../../frontend/src/charts.js))

- **Which charts:** a chart spec can declare `drill(index) → { title, query, n }`. Two do:
  - "Qual fruta chega" (fruit type);
  - "Taxa de podres por setor" (sector).
- **What a click does:** opens the side panel listing the 50 most recent fruits behind the bar, with the total, using the Painel's filters plus `review=no`. That is exactly the set the statistics count (they exclude fruits sent to review), so **the total equals the bar's n**. A test checks it against the database.
- **The connector:** a 2 px line from the clicked point to the panel. It is a rotated element that grows with `scaleX`, so it is transform-only.
- **Hint:** a line under the chart says "Clique numa barra para ver as frutas por trás dela", and the cursor becomes a pointer over bars.

### 5.10 Which data the Painel opens on ([views/DashboardView.vue](../../frontend/src/views/DashboardView.vue))

Every Painel statistic needs weeks of history:
- growth needs 2 complete periods;
- the forecast needs 8 periods of 30 or more fruits;
- the normal curve needs 3 or more periods.

With the real data on this machine (3 photo analyses, all from one day), the "Reais" view could only say "Dados insuficientes" on every card.

**What the Painel does:**
- **The check:** when no data source is chosen in the URL, it first asks the API for the oldest and newest real event (`/api/events?source=real&order=asc|desc&size=1`).
- **The switch:** if they are **less than 14 days apart**, it opens on **Demonstração** and shows a notice. Example: "Os dados reais ainda são poucos (3 análises em 1 dia(s)) para estas estatísticas… Mostrando dados de demonstração (sintéticos). Em “Dados”, escolha “Reais” para ver só os seus." With no real data at all, a shorter sentence is used.
- **Labelling:** the DEMO badges stay on every card. The certificate button then produces the demo certificate, which is also labelled as demonstration.
- **No layout shift:** the page body renders only after the source is decided, so the notice does not push content down. Measured CLS was 0.078.
- **Opting out:** choosing "Reais", or opening `/painel?source=real`, shows real data only, with the honest empty state.

**Nothing synthetic is written as real data.**

**Showcase completeness.** The synthetic history now also covers the two camera lines (see [docs/guides/showcase.md](showcase.md)), so every per-sector chart is drawn for every sector.
- **Demo certificate:** 49 pages, forecasts "9 de 9 com dados suficientes".
- **States that remain are the designed showcase behaviours:** few periods (oeste, vale), no backtest (vale), no variation (controle), and normality rejected.

---

## 6. Motion

All motion is transform/opacity. Every piece has a static fallback, and the "reduzir animações" toggle (`:root[data-motion="reduced"]` plus `reducedMotion()` in JavaScript) switches it off.

| Effect | How | File |
|---|---|---|
| Scan sweep while the photo is analysed | (existed) | UploadView, style.css |
| Reticles lock onto the box | SVG corner paths, `@keyframes lock`: scale 1.7 → 0.94 → 1 with a small rotation, 0.18 s stagger per detection | UploadView, style.css |
| Verdict chip pops | (existed) `pop` | style.css |
| Confidence ring fills | Two half-rings, each in a clipping half, rotated by WAAPI: right half 0→180°, then left half. The rotation **is** the fill, so it is transform-only. Label: "Confiança do modelo 69,4%" | [ConfidenceRing.vue](../../frontend/src/components/ConfidenceRing.vue) |
| Counters tick to the real values | `tween()` in control.js (ease-out cubic, rAF). The last frame is the exact value | UploadView, WhatIf |
| Painel charts draw in staggered, hover dims the other series, filter changes morph the chart, number tickers | (existed) | ChartBox |
| Sonar pulse on ATIVO | `::after` ring, `scale 1 → 3.2` with fading opacity, 2.4 s loop | style.css (`.sonar`) |
| Drill-down connector | §5.9 | FruitInspector |
| Page transitions | View Transitions: `routeTransitions(router)` starts a transition in `beforeResolve` and completes it after the new page renders. Without the API (or with reduced motion), the existing CSS route transition is used | control.js, router.js, App.vue |
| Thumbnail → inspector | `view-transition-name: fruit-shot` on the clicked thumbnail, then on the inspector image | control.js, style.css |
| Magnetic primary buttons | `vMagnetic`: translate up to 3 px towards the pointer. Only with a fine pointer (mouse) and without reduced motion | control.js (Analisar, Entrar) |
| Shaped skeletons | (existed for the Painel) and new `.sheet-loading` rows | style.css |
| Side panel and command bar entrance | `sheet-in` (translateX + opacity), `cmd-in` (translateY + scale) | style.css |
| Pipeline: camera → detecção → classificação → evento → estatística → relatório | 6 SVG icons with connectors, revealed step by step by WAAPI (0.56 s apart). Live status "Passo i de 6"; Repetir; the classification step carries an **IA** chip, the others **CÓDIGO**. **Pauses when scrolled off-screen** and resumes when back | [PipelineFlow.vue](../../frontend/src/components/PipelineFlow.vue) (Como funciona, above the existing 7-step technical pipeline) |

**No canvas, WebGL or animation library was added.**

**Reduced motion in detail.** The existing rule shortens every transition to 0.01 ms instead of removing it, so code that waits for "transition finished" still runs. The new elements that change state while the user waits get **no transition at all** under reduced motion (OS setting or toggle):
- the status chips;
- the upload progress bar;
- the what-if and replay bars;
- the magnetic buttons.

**Why:** the full test run caught the chips' 0.01 ms colour transitions "running" at the moment the upload started.

---

## 7. Video and images

### What exists (kept, checked by tests)

| Video | Role | Rules met |
|---|---|---|
| `demo` (Como funciona) | recording of the real app | WebM + MP4, poster, captions (VTT) and transcript, keyboard play/pause, plays only while visible, poster under reduced motion or Save-Data |
| `bg-esteira-real` (login) | third-party clip, labelled "Imagem ilustrativa" | poster fallback, **now with a keyboard pause button** |
| `bg-esteira-simulada` (Linha) | own simulation, labelled SIMULAÇÃO | poster fallback, **now with a keyboard pause button** |

**Pause buttons on background videos.** WCAG 2.2.2 requires a way to pause any moving content that loops for more than 5 seconds. The button (`.bg-toggle`) has `aria-pressed` and a label that changes between "Pausar vídeo de fundo" and "Reproduzir vídeo de fundo".

**Reduced-motion toggle.** Both video components now react to the in-app toggle immediately: the video is removed and its poster shown.

### New: "primeira análise" (first analysis)

- **Made by** [tools/record_clip.py](../../tools/record_clip.py), with **Playwright `recordVideo`** of the real app on a throwaway database. It logs in through the API, so no password is typed on screen.
  - **Content:** choose Caju and a sector, upload the third-party cashew photo, the live strip runs through its real states, the real model result appears, the inspector opens, and the record appears in History.
  - **Captions:** five pt-BR cues, written from the same step markers as the transcript, so they cannot drift.
- **Encoded** with ffmpeg (the copy bundled by `imageio-ffmpeg`): **WebM/VP9 609 KB + MP4/H.264 490 KB, 1280×720, 18.8 s, no audio.**
- **Poster:** taken at the result moment.
- **Badge:** "Gravação do app real · foto real". The video component used to say "dados sintéticos" for every clip; it now takes a `badge`, so this clip is not mislabelled.
- **Registered** by [tools/build_media.py](../../tools/build_media.py):
  - **Clip list:** the earlier hard-coded `demo` block is now a loop over `CLIPS`. `demo` keeps exactly the same entry.
  - **Formats:** the poster in AVIF/WebP/JPEG at 480/960/1280.
  - **Licence manifest:** a first-party entry in `licenses.json` listing all 12 files. The third-party photos visible inside the recording are listed under their own licences.
- **Where:** the History empty state (no real analyses yet). The video loads only when it scrolls near and plays only while visible.

**Determinism.** Rebuilding the media gave **byte-identical** files for every existing asset except one re-encoded background WebM, which only got a new content hash. The build used to delete the whole `media/` folder first. On this machine Windows refused to delete the (OneDrive-synced) folder halfway through, after its 7 videos were already gone. They were restored from git, and the build now deletes only the files.

### Live camera on Linha: simulation built from real cashew photos

**What the Linha page showed.** It said "Câmera desconectada" whenever the camera worker was not running.

**Search for real footage.** A search on Wikimedia Commons (the only source with automatic licence checks in this project) found **no freely licensed fixed-camera footage of cashews on a conveyor**. It found a cashew-chain documentary with people and narration, and old strawberry newsreels.

**Decision: 2D, seen from above.** The real installation is a fixed camera looking straight down at the belt, so its image is essentially 2D. A 3D animation would show a perspective the installed camera never has.

**What the simulated camera shows.**
- **The fruits:** cashews cut out of real photos from the public dataset used for training (Coffee and Cashew Nut), moving on a virtual belt. The `SimulatedBelt` sprite path already supported this.
- **The processing:** the camera worker (`run_camera`, `source: "sim"`) runs them through **the same code as a real camera**: segmentation, tracking, counting at the line, one event per fruit.

**Building the crops.** [tools/build_sim_crops.py](../../tools/build_sim_crops.py) builds `assets/media_src/belt_crops/` (53 crops, 1.7 MB, with `sources.json` listing photo, class, licence and modifications). It keeps only crops with:
- a GrabCut mask;
- a compact shape (solidity ≥ 0.92);
- a smooth surface (Laplacian texture < 4). This drops tufts of leaves annotated as fruit; on a contact sheet, all foliage scored ≥ 6.8 and fruit ≤ 6.7.

**Loading the crops.** `crop_pool()` in [belt/simulate.py](../../belt/simulate.py) loads them with the 4 rotations × 2 mirror images a fruit can show on a belt (424 views). `config/cameras.json` points both lines to the folder (`sim.crops`).

**Labels and honesty.**
- **Classes:** they come from the dataset's annotations (which can be wrong), not from the model.
- **On the frame:** the stamp says "SIMULAÇÃO · cajus de fotos reais · rótulos do conjunto", and the pill says "Simulação".
- **Under the frame:** the caption says the fruits are crops of real photos from a public dataset and links to the credits page.
- **In storage:** events are stored as demo (`is_demo`).

**Fixed on the way.** The worker only refreshed its status on snapshots, so after stopping it could report one fruit fewer than it had stored (34 vs 35, caught by `test_worker_stores_one_event_per_counted_fruit_and_publishes_a_frame`). It now writes a final status.

**For the pitch.** `scripts/pitch.ps1` starts both simulated cameras in the background, runs the site, and stops the cameras when the server stops. `-Seed` refreshes the demo data first.

### Checklist: media that could not be made honestly

The spec asks for an "onboarding guide for taking a good photo" video. That needs **real footage of someone photographing a fruit**. Generating it, or using stock footage presented as ours, is not allowed. To add it, place:

1. `assets/media_src/video/guia-foto.mp4` (or `.mov`): your own footage, 5–15 s, a person photographing one cashew on a plain light background, phone held above. No faces, or with consent.
2. A line in this document, or in `assets/media_src/catalog.json`, saying who filmed it and the licence (your own material).

Then run `python tools/build_media.py`, and the clip can be added to the photo guide the same way as `primeira-analise`.

The images the spec lists (fruit cards for caju, castanha and melão; photo-guide examples) **already exist**: licensed, AVIF/WebP/JPEG with `srcset`, explicit sizes and pt-BR alt text, each with an "Imagem ilustrativa" badge and credit.

---

## 8. Performance and budgets

Full report: [visual/perf.md](../reports/visual/perf.md). In short:

- **Budget (transferred, cold cache, 360 px), enforced by `test_360px_layout_and_page_weight_budgets`:**
  - `/inspecao` ≤ 190 KB, `/painel` ≤ 210 KB, `/historico` ≤ 200 KB (new);
  - the other pages are unchanged.
- **Lazy-loaded features:** the inspector, command bar, what-if, replay, ring and History are separate chunks, loaded on first use.
- **No new font and no new library.**
- **Layout-shift fix.** While measuring, CLS was 0.485 on both pages. The footer rendered before the page's code loaded, and then jumped down. `main` now reserves the viewport height, so the footer starts below the fold: **CLS 0.000 on /inspecao, 0.070 on /painel.**

---

## 9. Tests

| File | What it proves |
|---|---|
| [core/tests/test_control.py](../../core/tests/test_control.py) (7 tests, no browser) | **Endpoints:** need a login; every invalid filter returns 400; rows, filters and pages equal independent ORM queries. **Inspector:** shows exactly the stored fields (and never box, probabilities or crop). **Thumbnail:** only for the uploader; other users, demo rows, missing files and hostile names get 404. **What-if:** the histograms give **exact** "confidence < t" counts at all 101 thresholds (including 0.57 and 0.29999999999999999). **Replay:** columns end at the Linha page's lot totals. **Lot list:** the counts are correct |
| [core/tests/test_control_browser.py](../../core/tests/test_control_browser.py) (11 tests, Edge) | **Command bar:** keyboard open, navigate, select and close; every route reachable from it; a lot and an `#id`. **Inspector:** matches the stored row (photo and camera), the crop canvas is painted, the probabilities equal the response. **Live strip:** goes through the real states; the ring, counters and the time equal the response. **What-if:** page numbers equal ORM counts at 5 thresholds. **Replay:** ends at the table's n, % rotten and % low quality. **Drill-down:** total equals the ORM count, and the connector is drawn. **Traceability:** focus shows the source. **Themes:** axe in both themes on 8 pages; the logo matches the theme; the toggle persists. **Reduce-motion toggle:** 0 running animations and 0 videos; live switch to posters. **Videos:** poster, captions, transcript, keyboard pause, background pause; every image has alt text. **360 px:** History, inspector and command bar have no overflow; CSV export works |
| `core/tests/test_layout.py`, `core/tests/test_media.py` (updated) | Same checks as before. **Updated for the spec:** the new route, the "Limiar de revisão" section, the new top-bar controls in the focus order, `color-scheme: dark light`, and a `/historico` budget |
| `frontend/tests/series.test.mjs` | Motion budget: every keyframe and transition animates only transform/opacity (now 22 keyframes) |
| `core/tests/test_showcase.py` | Every synthetic Painel fruit has a model class and a confidence (see docs/guides/showcase.md) |

**Command:** `DJANGO_SECRET_KEY=… DJANGO_HTTPS=0 python manage.py test core -v 2`.

**Output:** [visual/after/test_output.txt](../reports/visual/after/test_output.txt). The summary is in §9.1 below.

### 9.1 Executed result

**Full suite, final build:** `python manage.py test core -v 2` → **`Ran 122 tests in 879.703s` — `OK`**. Output: [visual/after/test_output.txt](../reports/visual/after/test_output.txt).

**Node:** `node --test frontend/tests/series.test.mjs` → 2 pass, 0 fail, including "checked 22 keyframes and 16 transition declarations". The 9 chart tests skip in a bare Node run; they run inside the Django suite, which generates their fixtures.

**Build:** `npm run build` succeeds ([visual/after/bundle.txt](../reports/visual/after/bundle.txt)).

**Earlier runs of the final suite failed, and each failure was a real problem, now fixed:**
- **Logo seam** (the baseline run): the logo did not blend into the top bar.
- **Overflow:** a visually hidden table header widened the Linha page to 616 px on phones.
- **Budget:** the Créditos page went 40 bytes over its 125 KB budget, which led to the CSS split.
- **Reduced motion:** the chips' 0.01 ms transitions were caught "running".

The run before the line-history change was stopped and repeated, because the frontend was rebuilt while its browser tests were running.

**Excerpts of the real output (new tests):**

```
anonymous: {'/api/events': (403, 'not_authenticated'), '/api/events/thresholds': (403, 'not_authenticated'), '/api/events/1': (403, 'not_authenticated'), '/api/events/1/image': (403, 'not_authenticated')}
15 invalid list queries -> [400]; 7 invalid threshold queries -> [400]
classes ['baixa_qualidade', 'boa', 'podre']; n [10, 10, 410]; no confidence 3 of 433; 101 thresholds x 3 classes, mismatches 0; model {'version': 'belt_v2', 'reject_below': None}
owner 200 image/jpeg (320, 240) cache 'private, no-store'; other user 404; demo/missing/hostile name [404, 404, 404]; other user's detail image flag False
lots replayed to the line-page totals: L1-1006-01 n=10765 {'boa': 6497, 'baixa_qualidade': 2524, 'podre': 1415, 'revisar': 329}; L1-1006-02 n=10525 {'boa': 6373, 'baixa_qualidade': 2458, 'podre': 1403, 'revisar': 291}; lot list for the command bar: ['L1-1006-01', 'L1-1006-02']
command bar: /historico      input focused True, 0 arrow presses, active 'PÁGINAS Histórico', still open after Enter False
Esc closes True; 'L1-1006-01' -> 'Reprodução do lote L1-1006-01'; '#50898' -> 'Fruta #50898'; visible hint ['Control+K Meta+K', 'Ctrl K']; page errors []
inspector camera #148481: fields shown ['label', 'confidence', 'deformity_type', 'timestamp', 'sector', 'fruit_type', 'lot', 'camera', 'track_id', 'size_mm', 'needs_review', 'decided_by', 'model_version', 'source', 'id']
phases ['enviando', 'analisando', 'concluido']; strip 'Inferência 252,8 ms (medida no servidor) · Ida e volta 0,6 s (medida no navegador)'; response inference_ms 252.8 confidence 0.6944; counters {'conf': '69,4%', 'ms': '252,8 ms', 'ring': 'Confiança do modelo 69,4%', 'turn': 'matrix(-1, 0, 0, -1, 0, 0)'}
what-if 0.57  page {boa: 14556, baixa_qualidade: 6642, podre: 3143, revisar: 88} = ORM {'boa': 14556, 'baixa_qualidade': 6642, 'podre': 3143, 'revisar': 88}
replay L1-1006-01: table n 3.484, podres 14%, baixa 24,1% | replay at half ['1.065', '402', '223', '52'], at end {'boa': 2095, 'baixa_qualidade': 814, 'podre': 475, 'revisar': 100}, podres 14%
drill on 'Frutas por trás de: Caju': '24.981 eventos; mostrando os 50 mais recentes'; ORM count 24981; connector drawn True
trace /painel?source=demo [data-stat] > .badges .n-badge: 8 elements; focus shows ['Fonte: GET /api/stats/overview · período semana · setor todos os setores · dados demonstração · n = 26.169', 'trace-tip']
axe light /painel?source=demo      no violations
logos {'dark': {'variant': 'on-dark', 'corner': 'rgb(20, 35, 30)', 'bar': 'rgb(20, 35, 30)', 'footer': 'on-dark', 'html': 'dark'}, 'light': {'variant': 'on-light', 'corner': 'rgb(245, 241, 230)', 'bar': 'rgb(245, 241, 230)', 'footer': 'on-dark', 'html': 'light'}}; toggle -> ['light', 'light', 'on-light']; after reload light
live toggle on /: before [1, 'video']; after [0, 'poster', 'reduced', 'true']; running animations after []
video on /historico: {'id': 'primeira-analise', 'poster': '/static/media/primeira-analise-poster.1280.b2003ddf3b.webp', 'muted': True, 'track': True, 'transcript': 5, 'paused': True, 'pressed': 'false', 'badge': 'Gravação do app real · foto real'}ok
background video after Space on its pause button: paused True, aria-pressed true, label 'Reproduzir vídeo de fundo'
360px: [('historico', 0), ('inspetor', [0, 360]), ('comandos', [0, 341])]; selection '2 selecionados · Baixa qualidade 1 · Boa 1 · confiança média 92,6%'; CSV 3 lines, header id;timestamp;sector;fruit_type;label;is_good;deformity_type;…
```

---

## 10. Files changed

**New:**
- **Back end:** `core/event_views.py`, `core/tests/test_control.py`, `core/tests/test_control_browser.py`.
- **Front end:**
  - `frontend/public/theme.js`, `frontend/src/control.js`, `frontend/src/control.css`;
  - components: `ConfidenceRing.vue`, `FruitInspector.vue`, `LotReplay.vue`, `CommandBar.vue`, `WhatIf.vue`, `PipelineFlow.vue`;
  - views: `HistoryView.vue`.
- **Tools and scripts:** `tools/record_clip.py`, `scripts/perf_report.py`.
- **Recording sources:** `assets/media_src/video/primeira-analise.{webm,mp4,vtt,json}` and `primeira-analise-poster.png`.
- **Docs:** `docs/plans/control_room.md`, `docs/guides/control_and_motion.md`, `docs/reports/visual/*`.

**Changed:**
- **Back end:** `fruitcam/urls.py` (4 routes).
- **Front end:** `frontend/index.html`, `style.css`, `charts.js`, `media.js`, `api.js`, `router.js`, `strings.js`, `App.vue`; views `UploadView.vue`, `DashboardView.vue`, `LineView.vue`, `HowItWorksView.vue`, `LoginView.vue`; components `ChartBox.vue`, `StatCard.vue`, `BackgroundVideo.vue`, `LoopVideo.vue`, `CameraDiagram.vue` (gradient colour now a token).
- **Media build:**
  - `tools/build_media.py` (clip loop, file-only cleanup);
  - `frontend/src/media.json`, `frontend/src/licenses.json` (regenerated);
  - `frontend/public/media/…`: the new clip's files, and one re-hashed background WebM.
- **Tests and scripts:**
  - `core/tests/test_layout.py`, `core/tests/test_media.py` (expectations for the new UI; both stylesheets);
  - `frontend/tests/series.test.mjs` (motion budget over both stylesheets);
  - `scripts/layout_screenshots.py` (theme option, History page).
- **Showcase:** `core/showcase.py`, `core/tests/test_showcase.py`, `core/management/commands/seed_showcase.py`, `docs/guides/showcase.md`: sorting fields and camera-line history.

**Not touched:** the model, `training/infer.py`, `core/inference.py`, authentication, upload validation, and the analytics maths (`analytics/fruit_analytics.py`, `core/stats.py`, `belt/stats.py`).

---

## 11. What was not verified

- **Real phones, other browsers and real frame rates:**
  - No real phone. Everything ran in **headless Microsoft Edge** (Chromium) through Playwright.
  - Firefox and Safari were not run. The CSS `content: "…" / ""` alternative-text syntax and the View Transitions API are Chromium-first; other browsers fall back (no glyph, or no transition), which was not observed.
  - **Frame rate** on a mid-range phone was not measured. The animations follow the transform/opacity rule, but 60 fps was not measured on any device.
- **Colour:**
  - Colour rendering on real screens, and the light theme in bright daylight, were not checked.
  - Contrast was checked by axe on the rendered DOM. axe cannot check text drawn inside chart canvases.
- **People:**
  - The **feel** of the interactions (magnetic buttons, sonar, reticles, replay speed) was not tested with real users.
  - The usefulness of the command bar entries and of the drill-down was not tested with real users either.
- **Performance:**
  - The report is a **Lighthouse-equivalent** run with CPU and network throttling in Edge, not Lighthouse itself.
  - **INP** (real responsiveness) needs field data and was not measured.
- **Before/after comparison:** the "before" timing metrics (LCP, CLS, TBT) were not measured before the change. Only the before **page weights** (from the baseline test run) and bundle sizes are available.
- **Screen readers:** the dialogs, combobox, tooltips and live regions follow the WAI-ARIA patterns and pass axe, but were not tried with NVDA, JAWS, VoiceOver or TalkBack.
- **The thumbnail endpoint** was tested with the app's own uploads, not with very large or unusual PNGs.

---

## 12. Future: not built, because the data does not exist

- **Store the box, crop and per-class probabilities of each photo event.** The inspector could then show them for history, not only for the fresh result.
- **Several detections per photo.** Only then would the "tracking trail between boxes" animation have a real case.
- **Per-event camera crops.** Today only the latest frame per camera is kept.
- **Lots for photo events.**
- **Review, relabel and feedback writes.** They need a reviewed-label table with an audit trail and a review screen. Only after that should the inspector offer "corrigir classe".
- **A calibrated review threshold for the model** (`reject_below`). Until it exists, the real threshold stays "nenhum" and the what-if remains a simulation.
- **Field accuracy:** "ainda não avaliado" until measured on held-out real conveyor images, with the test named.
- **The photo-guide onboarding video**, which needs supplied footage (checklist in §7).
