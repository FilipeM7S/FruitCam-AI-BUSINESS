# Layout plan (written before implementation)

## 1. What exists today (Step 0 inventory)

**Routes** ([frontend/src/router.js](../../frontend/src/router.js)):

| Route | View | Access | Content |
|---|---|---|---|
| `/login` | LoginView | public | login card over the USDA belt video |
| `/` | LineView | login | big hero with belt-simulation video; "Como a câmera funciona" (diagram + 6 steps); "Linha ao vivo" (camera/period/data selectors, live frame, 4 KPIs, flow chart, control chart with alarms, lot table) |
| `/inspecao` | UploadView | login | banner; form card (sector, fruit type, drop zone, camera/analyse buttons) beside a result card that shows the photo guide, then the annotated image, verdict, probabilities and model facts |
| `/painel` | DashboardView | login | header with demo badge; filter form (period, sector, start, end, data source); 8 statistic cards in one flat grid: deformity, forecast, fruits, growth of good, growth of rotten, recurring, Gaussian + Q-Q, overview (last) |
| `/como-funciona` | HowItWorksView | public | banner; pipeline animation; 8 figures; model quality text; "not evaluated" list; demo video; verified / not verified |
| `/creditos` | CreditsView | public | third-party photos; training/evaluation datasets; own material |

**Navigation**: one horizontal top bar (`.topbar`) shown only when logged in: logo, four links (Linha, Inspeção por foto, Painel, Como funciona), user name and "Sair". Créditos is reachable only from the footer. Logged-out visitors of public pages see no navigation. A fixed "?" button opens the user guide on every page.

**Layout components**: `App.vue` (shell), `StatCard.vue` (dashboard card, `wide` prop spans two columns), `ChartBox.vue` (canvas, empty states, badges; creates the chart when it scrolls into view), `BackgroundVideo.vue`, `ResponsiveImage.vue`, `GuideDialog.vue`.

**CSS approach**: one global stylesheet, `frontend/src/style.css` (3,302 lines), no component styles, no CSS framework. Colour tokens exist in `:root`; spacing has a single token (`--gutter: 16px`). Measured in the file: 25 different pixel values in padding/margin/gap declarations (most common 6, 8, 12, 14 and 10 px), the content width `1160px` repeated in 4 rules, 18 different grid templates, and media queries at 640, 960 and 1024 px only.

**Bundle before** (`npm run build`, saved in [before/bundle.txt](before/bundle.txt)): 20 precompressed files, 2,115,598 B raw → 735,360 B Brotli. Largest chunks: charts 203.1 KB, strings 90.0 KB, index 51.8 KB, CSS 40.5 KB.

**Tests before**: `python manage.py test core -v 2` → Ran 67 tests in 720.164 s, OK; `python test_fruit_analytics.py` → 64/64 ([before/test_output.txt](before/test_output.txt)).

**Screenshots before**: [before/](before/) — every page at 360, 768 and 1280 px, plus the inspection result.

## 2. Information architecture

One product, three jobs: **operate the line**, **analyse the history**, **understand and trust the system**.

| Navigation group | Page | Purpose | Main change |
|---|---|---|---|
| Operação | **Linha** (`/`) | what the camera sees now | live monitor first; the camera explainer stays on this page, after the monitor; the hero becomes the page header (title, one-line description, actions) |
| Operação | **Inspeção por foto** (`/inspecao`) | check one fruit off the line | the photo (drop zone, preview, then the annotated result image) and the result panel sit side by side on desktop, result below the photo on mobile |
| Análise | **Painel** (`/painel`) | history and statistics | sticky filter bar (period, sector; more filters folded); the 8 statistics grouped into labelled sections, overview first |
| Sobre | **Como funciona** (`/como-funciona`) | method, figures, honest limits | consistent section headers; content unchanged |
| Sobre | **Créditos** (`/creditos`) | licences and attribution | now in the navigation, not only in the footer |
| User menu | **Sair** / **Entrar** | account | logged-out visitors of public pages get a top bar with "Entrar" |

Dashboard sections (all 8 statistics, charts and honesty states unchanged):

1. **Visão geral**: overview (volume, rotten rate, rate by sector), full width.
2. **Qualidade agora**: dominant defect (wide) and fruit received (narrow), side by side from 1280 px.
3. **Tendências**: growth of good and growth of rotten as a pair (side by side from 1024 px, stacked below), then the recurring histogram (full width).
4. **Distribuições**: Gaussian fit with Q-Q plot per sector (full width).
5. **Previsão**: forecast per sector (full width).

**Future pages** (do not exist, not created): a review screen to decide fruit sent to *revisar*; a tray-recording screen for `record_tray`; camera configuration; report export.

## 3. Layout system

- **Shell**: skip link → top bar (logo, user menu) → navigation → main → footer. Navigation is one `<nav class="nav">` element: a fixed left **sidebar** from 1024 px, a fixed **bottom bar** with icons and short labels below 1024 px. The active route is marked by vue-router's `aria-current="page"` and a visible indicator. The "?" button sits above the bottom bar on small screens.
- **Tokens** in one place (`:root` of `style.css`): spacing scale `--space-1` … `--space-11` = 2, 4, 6, 8, 12, 16, 20, 24, 32, 48, 64 px (existing off-scale values round to the nearest step, ties upward: 10→12, 14→16, 18→20, 22→24, 28→32), `--content-max`, `--form-max` (login card, tab bar), `--thumb` (fruit thumbnails), `--sidebar-w` (232 px from 1280 px; an 88 px icon rail `--rail-w` from 1024 px), `--topbar-h`, `--bottombar-h`, `--page-x` (gutter per breakpoint), `--card-pad`, `--gap`, `--section-gap`, grid `--cols`.
- **Breakpoints**: base (from 360 px), 768, 1024, 1280. The old 640 and 960 queries move to 768 and 1024.
- **Grid**: a 12-column grid for the dashboard (4 columns on phones, 8 from 768, 12 from 1024). Card sizes by chart type: `span-full` (wide time series and per-sector multiples), `span-half` (paired charts, 6 of 12 from 1024), `span-main` / `span-side` (8 + 4 from 1280).
- **Page header pattern** on every page: title, one-line description, actions on the right (stacked on phones). Banner pages keep their illustrative image with its credit.
- **Section heading pattern**: `h2` + one-line description, same spacing everywhere.
- Ad-hoc margins, paddings, gaps and widths become tokens; colours, typography, the Okabe-Ito chart palette, animations and reduced-motion rules stay as they are.

## 4. Unchanged on purpose

Chart code and math (`charts.js`, `series.js`), API calls, honesty states (insufficient data, n/a, poor fit, demo data, n badges, "Dados sintéticos"), animations and `prefers-reduced-motion` behaviour, all strings in `strings.js` (new ones are added there), the brand logo and colours.

## 5. Files

Change: `frontend/src/style.css`, `frontend/src/App.vue`, `frontend/src/strings.js`, `frontend/src/views/LineView.vue`, `UploadView.vue`, `DashboardView.vue`, `HowItWorksView.vue`, `CreditsView.vue`, `frontend/src/components/StatCard.vue` (span prop), `frontend/package.json` (axe-core as a dev dependency for the accessibility test).
Create: `core/test_layout.py`, `scripts/layout_screenshots.py`, `docs/layout/after/*`.

## 6. How it will be verified

Screenshots at 360, 768 and 1280 px in `docs/layout/after/`; a browser test asserting no horizontal overflow at 360 px on every page, every route reachable from the navigation, every dashboard statistic rendering its chart and its honesty states, an axe scan with zero serious or critical issues, and reduced motion still disabling animations; a static test that layout rules use the tokens and only the four breakpoints; the full existing suite; the build with bundle size before and after.
