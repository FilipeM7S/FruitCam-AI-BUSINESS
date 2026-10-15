# FruitCam AI: the site's visual identity

> **Superseded, 2026-10-06.** The multicolour layer described below (an accent per area, colour-cycled numbered sections, gradients) was replaced by the restrained "control room" theme: dark-first with a light theme, HUD strokes and corner brackets, one accent for "system active", and every colour a token. See [docs/guides/control_and_motion.md](control_and_motion.md) §4. The Fraunces display face, the area colours (now a small tick), and the rules in Part 4 still apply.

This document explains the visual layer of the web app:
- the colour system, with an accent per area of the site;
- the numbered, colour-coded sections;
- the display typeface;
- the decorative details.

It ties the site to the PDF certificate ([docs/guides/certificate.md](certificate.md)), so both read as one brand. The code has no comments; this file is the only place where it is explained.

**Status:** checked in headless Microsoft Edge at 1366 px and 390 px. The full test suite (103 tests) passed except for one test, which caught a real problem: the logo did not blend into the top bar. That was fixed and the test re-run (Part 5). Not checked on real phones or in other browsers.

---

## Part 1: what changed and why

**Before:** the app was a coherent dark ink-green, but monochrome. Every page, section and card used the same surfaces, so the eye had nothing to tell areas or sections apart.

**Now:** the same dark theme, with colour used for **orientation**, not decoration.
- **A colour per area:** each area of the site has its own accent, which appears in the navigation, the page header, the panel edges and the buttons.
- **Numbered sections:** the sections of every page are numbered and colour-coded, like the certificate's section openers.
- **Display face:** page and section titles use **Fraunces**, the certificate's display face.

---

## Part 2: the colour system

All colours are tokens in [frontend/src/style.css](../../frontend/src/style.css) (the theme layer at the end of the file).

| Token | Colour | Text tint (on dark) | Comes from |
|---|---|---|---|
| `--teal` | `#3fab94` | `#8fd3bf` | "_ai" in the logo |
| `--cashew` | `#e2553b` | `#ff9d86` | the cashew apple in the logo |
| `--gold` | `#e6b13c` | `#f2d27f` | the app's existing accent |
| `--tan` | `#c9a47a` | `#e6c9a2` | the cashew nut in the logo |
| `--sky` | `#56b4e9` | `#a7d8f5` | the charts' Okabe-Ito blue |
| `--violet` | `#a78bfa` | `#cdbefe` | a fifth section colour |
| `--spectrum` | cashew → gold → teal → sky | — | the top bar and footer rule |

**Accent per area.** Each route sets `meta.accent` in [router.js](../../frontend/src/router.js). [App.vue](../../frontend/src/App.vue) puts it on the app root as `data-accent`, and each navigation link carries its own `data-accent`. CSS then maps that to `--acc` and `--acc-text`:

| Area | Accent |
|---|---|
| Linha (and Entrar) | teal |
| Inspeção por foto | cashew red |
| Painel | gold |
| Como funciona | tan |
| Créditos | sky |

**Where the accent shows:**
- the soft glow behind the page;
- the active navigation item and every navigation icon (in its own area's colour);
- the wave under the page title;
- the top edge and tint of panels and filter bars;
- secondary buttons, the selected segment of segmented controls, the drop zone and the selected fruit card.

**Section colours.** On every page, sections cycle through teal, gold, cashew, sky and violet (`.section:nth-of-type(5n+k)` sets `--sec`).
- **Numbered chip:** each section title gets a number chip in its colour (`01`, `02`, … from a CSS counter, hidden from screen readers with `content: … / ""`).
- **Wave:** a woven wave under the section head, echoing the certificate's guilloché lines.
- **Cards:** the cards inside a section take its colour on their top edge.

**Fruit classes keep their meaning.** The KPI tiles on the Linha page use the chart colours for the class they show (green for boa, yellow for baixa qualidade, orange for podre, pink for revisar) as a tint and a top bar. The value text already used the matching text colour.

**Steps.** The 7 pipeline steps on Como funciona and the 6 camera steps on Linha each get a colour from the spectrum (number chip and top edge), with dark text on the light chip.

---

## Part 3: typography

**Fraunces** (licence in [LICENSES.md](../../LICENSES.md), credited on the Créditos page):
- **Use:** page titles (`h1`) and section titles.
- **File:** a single static weight, subset to Latin letters, punctuation and Portuguese accents, in WOFF2: **12.4 KB**.
- **Built by** [tools/build_fonts.py](../../tools/build_fonts.py) (`python tools/build_fonts.py --web-only`), which also builds the certificate's fonts.
- **Hosting:** the file sits in `frontend/src/fonts/` with its licence. Vite bundles it with a content hash, so it is cached as immutable.
- **Missing glyphs:** `font-synthesis: none` prevents fake bold. Any character outside the subset falls back to Georgia.

Everything else keeps the system font stack.

---

## Part 4: rules the theme respects

- **Spacing:** only the existing tokens (no raw pixel padding, margin or gap); no new breakpoints.
- **Motion:** no new motion; every existing animation still moves only `transform` or `opacity`.
- **No blur, no fixed backgrounds.** The first version used `backdrop-filter` on the top bar and navigation and a `background-attachment: fixed` glow. In headless Edge that exhausted the renderer (`ERR_INSUFFICIENT_RESOURCES`, and the login page stopped responding). Both were removed: the bars are now opaque gradients, and the glow scrolls with the page. Slow phones benefit too.
- **The top bar is exactly the logo plate colour.** An early version tinted the top bar with 4% of the area accent. The logo's dark plate (`#14231e`) then no longer matched the bar and showed as a faint box. `test_logo_is_the_dark_variant_and_blends_with_the_bar` caught it, and the tint was removed.
- **The sticky filter bar stays sticky.** An early version set `position: relative` on all filter panels, which broke the Painel's sticky bar. The accent edge is now an inset shadow.
- **Colour never carries meaning alone.** Section numbers and titles name the section; classes keep their labels.

---

## Part 5: verification

- **Screenshots:** every page at 1366 px and 390 px before and after, reviewed by eye. The project's own screenshots in [docs/reports/layout/after/](../reports/layout/after) were regenerated with `python scripts/layout_screenshots.py docs/reports/layout/after`.
- **Painel charts:** canvases checked for painted pixels after the change (they paint; below-the-fold charts are created lazily, as before).
- **Test suites:** full run `python manage.py test core -v 2`, output in [docs/reports/visual/before/test_output.txt](../reports/visual/before/test_output.txt): `Ran 103 tests`, 102 passed. The one failure was the logo/top-bar mismatch above. After the fix, that test was re-run on its own and passed (`top bar: logo on-dark, corner rgb(20, 35, 30) vs bar rgb(20, 35, 30)`). The run covers `core.tests.test_layout`, `core.tests.test_media` and `core.tests.test_dashboard`:
  - spacing tokens, breakpoints, overflow at 360 px, focus order;
  - **axe accessibility with no serious or critical issues** (including colour contrast);
  - reduced motion;
  - page-weight budgets (the font fits even the 125 KB Créditos budget);
  - dashboard behaviour.
