# FruitCam AI: the PDF certificate

The Painel has a **"Baixar certificado (PDF)"** button. It downloads a formal certificate for the filters currently selected. The certificate contains:
- the FruitCam_ai logo and our declarations;
- the statement **"A inteligência Artificial pode cometer erros."**;
- every statistical chart and number of the Painel and of the Linha page;
- an executive summary, a technical sheet and a page for human sign-off.

This document explains the certificate's content, its visual identity, how it is built, and how it was verified. The code has no comments; this file is the only place where it is explained. The demo dataset used to show every behaviour is described in [docs/guides/showcase.md](showcase.md).

**Status:** checked in these ways, all on this Windows machine:
- automated tests with known synthetic answers;
- the real server driven by headless Microsoft Edge;
- every page rendered to images and reviewed.

It was **not** checked in other PDF viewers, printed on paper, or with real field data. See Part 7.

---

## Part 1: what the certificate contains

Every chart has a numbered figure title ("FIGURA 07") and sits above a table with its exact numbers, so nothing depends on reading a chart by eye.

| Part | Content |
|---|---|
| Cover | Logo on an ink band with guilloché lines, the title, the certificate number, the attestation, the scope in a grid, the AI statement, the issue date and user, the SHA-256 fingerprint, a **QR code**, and the **fingerprint rosette seal** |
| Sumário | Table of contents with page numbers (the PDF also has clickable bookmarks), plus **"Como ler este certificado"**: class colours, warning boxes, hatching, n/d, IC 95% |
| 01 Resumo executivo | **KPI tiles** (fruits, rotten rate with interval, sectors, reliable forecasts, camera fruits, rejected lots, alarms, records pending review), **Destaques** (sentences written from the data, e.g. "sul: previsão de 59,8% de podres; chance de mais podres que boas > 99%"), the scope and the summary table |
| 02 Declarações | The AI statement, what the document is and is not, the review exclusion count, and every honesty statement from the website, word for word (Part 3) |
| 03 Visão geral | Volume, rotten rate and sectors; **"Cobertura dos dados"**, a heatmap of fruits per sector and period showing gaps, new sectors and seasonality; **"Fichas por setor"**, one row per sector with a **sparkline** of its rotten share, interval, latest value, forecast state and normal-curve state |
| 04–07 | The Painel, card by card: defects per week, fruits, growth, recurrence (month, season, week of year), Gaussian fit and Q-Q plot per sector, forecast per sector, each with "Como ler" and the Painel's warning badges |
| 08 Linha de inspeção | Per camera: indicators with 95% intervals, flow, control chart, **size distribution by class**, alarms, and a **lot-acceptance chart** (each lot's rotten share with its 95% interval against the line's maximum, marked aprovado, reprovado or inconclusivo) |
| 09 Qualidade do modelo | The measured model quality shown on "Como funciona" |
| 10 Metodologia | Definitions of every statistic |
| 11 Ficha técnica | Generator version, typography, data counts, model file and its **SHA-256**, every statistical parameter, software versions |
| 12 Conferência humana | Lines for name, role, date, signature and notes. The AI can be wrong; a person signs off |
| Anexo A / B | Every value per period, and every control-chart window of each camera |
| Autenticação | A large rosette, the QR code, number, date, user, fingerprint, and how to check the document |

**On every inner page:**
- an ink header band with the app icon, the certificate number and a line of microtext;
- the running section title;
- a **section tab on the right edge** that moves down section by section, for finding sections in print;
- in the footer, **"A inteligência Artificial pode cometer erros."**, "Página X de Y", the start of the fingerprint and the issue time.

**Demo data:** when the scope includes demonstration data, every page has a diagonal "DADOS DE DEMONSTRAÇÃO" watermark, and the cover says so.

---

## Part 2: visual identity

The identity comes from the app itself:
- **Colours:** the app's ink background `#14231e`, the cream of the logo plate, cashew red, teal ("_ai") and cashew-nut tan.
- **Typography:** it echoes the logo, a confident wordmark with a monospace "_ai".

| Element | What it is |
|---|---|
| **Fingerprint rosette** | A guilloché rosette, the woven-line pattern used on banknotes, drawn as vector curves in teal, red and tan. The number of petals, the modulation and the phase of each layer come from the bytes of the certificate's **SHA-256 fingerprint**. Same data, same rosette; any change in the data gives a visibly different one. It is the seal on the cover and on the last page. The ring around it carries the certificate number |
| **Guilloché band and waves** | Interlaced sine waves on the cover band and under every section title |
| **Microtext** | Lines of 2.2–2.4 pt text repeating the number and fingerprint, along the cover border and under every header: a classic security-print detail |
| **QR code** | Plain text (no URL): issuer, number, issue time, scope, counts and the full fingerprint. ASCII only, so any reader decodes it |
| **Section openers** | A large red numeral (`03`) in Fraunces, a "SEÇÃO 03" kicker and the title |
| **Tables** | Ink header with a red underline, zebra rows in warm cream |
| **Typography** | **Fraunces** (a soft display serif) for titles and the attestation, **Inter** for text, tables and the charts (the app's own font stack starts with Inter), and **JetBrains Mono** for numbers, codes and the fingerprint (echoing "_ai") |

**Fonts:**
- **Bundled in the project:** [assets/brand/fonts/](../../assets/brand/fonts), The licence is recorded in [LICENSES.md](../../LICENSES.md) and its full text is in `legal/texts/`; the PDF's technical sheet names the fonts.
- **Static weights:** [tools/build_fonts.py](../../tools/build_fonts.py) downloads the variable fonts from the Google Fonts repository and pins the weights the PDF uses, with fontTools (already installed with matplotlib). Run it again to rebuild them.
- **Fallback:** if the folder is missing, the certificate falls back to DejaVu, still complete, and the technical sheet says so.
- **Missing glyph:** Fraunces has no "✓", so the Authentication opener draws that glyph in Inter. A check for missing glyphs makes this automatic.

---

## Part 3: the declarations, and where their text comes from

The declarations are the honesty statements the website already shows, copied **word for word** into [core/certificate_text.py](../../core/certificate_text.py) (`DECLARATIONS`):

| Declaration | Website source (`frontend/src/strings.js`) |
|---|---|
| Prototype status | `t.footer.honesty` |
| Confidence is not accuracy | `t.upload.confidenceNote` |
| Main limitation | `t.how.limits` |
| Training data correction | `t.how.dataIssue` |
| What was verified / not validated / not evaluated | `t.how.verified`, `t.how.notVerified`, `t.how.pending` |

A test reads those strings from `strings.js` with Node and fails if any differs from the Python copy.

**Text written for the certificate that the website does not have.** Please review it; these are statements in your company's name.
- "Natureza deste documento": the certificate documents automatically calculated statistics; it is not a quality report, does not guarantee any fruit or lot, and does not replace human inspection.
- The sentence that fruits pending review are excluded from the Painel, with their count.
- The attestation on the cover and the demonstration-data notices.
- The "Conferência humana" sentence: a responsible person should check the results before any decision.

The AI statement is used exactly as you wrote it, including the capital "A" in "Artificial". It is one constant (`AI_ERRORS`).

---

## Part 4: how it works

```
Painel → "Baixar certificado (PDF)" ── GET /api/certificate?period&sector&start&end&source
                                         │  (same filters and validation as /api/stats)
                                         ▼
                        certificate_data.collect
                          ├ stats.load_events → every stats builder (identical to /api/stats)
                          ├ every camera → belt.stats.summary (+ size histograms)
                          ├ coverage matrix (fruits per sector and period)
                          ├ model evaluation (frontend/src/figures.json)
                          └ SHA-256 fingerprint of all of the above
                                         ▼
                        certificate_pdf.render
                          ├ certificate_charts (matplotlib, Inter, 220 dpi PNG)
                          └ reportlab: cover, openers, tables, rosette, QR, TOC, bookmarks
                                         ▼
                        application/pdf · certificado-fruitcam-FC-AAAAMMDD-XXXXXXXX.pdf
```

### Files

- **[core/certificate_data.py](../../core/certificate_data.py)** collects everything the certificate shows.
  - **Painel numbers:** it loads the events once and runs every builder in `stats.BUILDERS`, so the numbers are the Painel's numbers (a test checks they are identical).
  - **Camera numbers:** each camera runs the Linha page's own code, with a window size that adapts to the period (at most 150 windows).
  - **Fingerprint:** the SHA-256 of the scope and every result, in canonical JSON. The issue time and the user are not part of it.
- **[core/certificate_charts.py](../../core/certificate_charts.py)** draws each chart with matplotlib's object API under a lock, in Inter.
  - **Colours:** the Okabe-Ito set, validated with a colour-blindness checker; text never uses the series colour.
  - **New charts:** the coverage heatmap (single-hue teal ramp, log scale), the lot-acceptance chart and the size distribution.
  - **Bars:** drawn as one shape collection per series, which is 2.5–5× faster than one shape per bar.
  - **Extreme outliers** get a cut scale with the value written on the cut bar (same rule as the Painel, see docs/guides/showcase.md).
- **[core/certificate_pdf.py](../../core/certificate_pdf.py)** builds the layout with reportlab.
  - **Fonts:** registered with a fallback to DejaVu.
  - **Pieces:** the cover and inner-page decorations, section openers, KPI tiles, sparklines, the rosette, QR code, microtext, the technical sheet and the sign-off page.
- **[core/certificate_text.py](../../core/certificate_text.py)** holds every pt-BR text in the PDF and the pt-BR number and date formatting.
- **[core/views.py](../../core/views.py)** `certificate` handles the request:
  - it requires login;
  - it validates the filters like `/api/stats`;
  - it returns `no_data` (404) when nothing is in scope;
  - otherwise it returns the PDF, with `no-store` and the number in `X-Certificate-Number`.
- **[core/stats.py](../../core/stats.py)**:
  - `scope()` holds the shared filters.
  - `rows()` reads a query with the timestamp cast to text and parses it with pandas. The output is identical and about 1.8× faster (see docs/guides/showcase.md, Part 5).
- **Frontend:**
  - [api.js](../../frontend/src/api.js) `download()`;
  - the button in [DashboardView.vue](../../frontend/src/views/DashboardView.vue), with busy state, error message and screen-reader announcement.

### Speed

Measured on the 3-year showcase (≈255,000 Painel and 95,000 camera events, 49 pages):
- **Collecting the data:** 4–6 s.
- **Building the PDF:** 10–13 s.
- **Large timing swings:** on some runs both steps took about twice as long (OneDrive was syncing the 47 MB database in the background).

What makes it this fast:
- **Draft pass:** the table of contents needs two layout passes, and the first one skips images and decorative vector paths, which don't change the layout.
- **Microtext:** the line is cut to width once, with cumulative glyph widths, and cached. The first version re-measured it character by character on every page: 9 million font lookups.

The 3 real records on this machine give a 19-page PDF in about 2 s.

### The certificate number and the fingerprint

- **Number:** `FC-AAAAMMDD-XXXXXXXX`. Each issue gets its own number.
- **Fingerprint and rosette:** both identify the **data**.
- **How to check a certificate:** issue it again with the same filters. If the data hasn't changed, the fingerprint and the rosette are identical.
- **No registry:** issued certificates are not stored, so a third party cannot look a number up (Part 7).

---

## Part 5: commands

```powershell
pip install -r requirements.txt     # reportlab (PDF) and pypdf (tests)
cd frontend; npm run build; cd ..
$env:DJANGO_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(50))"); $env:DJANGO_HTTPS = "0"
python manage.py seed_showcase      # optional: data that exercises every behaviour (docs/guides/showcase.md)
python manage.py test core.tests.test_certificate core.tests.test_showcase -v 2
python tools/build_fonts.py         # only to rebuild assets/brand/fonts
```

---

## Part 6: verification

### 6.1 Automated tests

- **Certificate:** [core/tests/test_certificate.py](../../core/tests/test_certificate.py).
- **Showcase:** [core/tests/test_showcase.py](../../core/tests/test_showcase.py).
- **Full run:** [certificate_test_output.txt](../reports/tests/certificate_test_output.txt).

| Test | Measured |
|---|---|
| Login and filters | 3 × 400 `invalid_filter`; empty database → 404 `no_data`; no login → 403 |
| Contents, known data (12 months; A 10%, B 30%) | AI statement on **every** page; all 7 declaration groups word for word; every section in the PDF bookmarks; 13 chart images; 24.000 fruits, 20,0% (Wilson 19,5% a 20,5%), B 30,0%, A 10,0% and the fruit tie found in the text; no watermark on real data |
| Identity | Fraunces, Inter and JetBrains Mono embedded; QR payload ASCII with the number and the full fingerprint; rosette layers identical for the same fingerprint and different for another; sections numbered 1…N; KPI tiles present |
| Same numbers as the Painel | 21 of 21 payloads identical to `/api/stats` (3 filter sets × 7 statistics) |
| Fingerprint | Same data → same fingerprint; one more fruit → a different one; 3 issues → 3 numbers |
| Demo watermark | On every demo page and the cover; 0 on the real certificate |
| Linha section | Counts equal the database; lot intervals and verdicts equal an independent recomputation; every alarm window overlaps the rejected lot |
| Declarations = website | 0 differences with `strings.js` |
| Browser | Real login, click, download of `certificado-fruitcam-FC-…pdf` starting with `%PDF`; busy label; screen-reader status; 0 px overflow at 390 px; empty database → alert |
| Showcase | Every designed behaviour present (docs/guides/showcase.md, section 6) |

### 6.2 Visual review

I rendered every page of the showcase certificate (49 pages), the real-data certificate (19 pages) and an all-sources monthly certificate (41 pages) to images and looked at all of them. The review caught and fixed these problems:
- the state of the last section leaking into the table of contents page (it is now reset at each layout pass);
- the table of contents running into section 01;
- clipped axis labels on the horizontal bar charts;
- a heading left alone at the bottom of a page, away from its chart;
- a missing "✓" glyph in the display font.

---

## Part 7: what was not verified, and known limitations

**Not verified:**
- **Other PDF viewers** (Adobe Reader, phone viewers) and **printing on paper**. The microtext (2.2–2.4 pt) and the rosette's 0.22 pt lines need a decent printer; on a cheap printer they may merge.
- **Scanning the QR code with a phone.** The payload is checked as text, but no phone scanned it. At 25 mm on the cover the modules are about 0.4 mm. The 40 mm code on the last page is the safer one to scan.
- **Real browsers other than headless Edge**, and real phones.
- **Real field data.** As with the Painel, the statistics were checked only on synthetic data.

**Known limitations:**
- **Generation is synchronous.** On the full showcase it takes 15–20 s and holds one server worker that long, with no rate limit. With many users, move it to a background job.
- **No registry of issued certificates.**
- **Charts are 220 dpi images.** The numbers are always in the tables as text.
- **reportlab does not kern or apply ligatures.** Large Fraunces titles are set without kerning.
- **The Linha section covers the whole scope period,** so its windows are coarser than the live Linha page's.

---

## Part 8: files

**New:**
- `core/certificate_data.py`, `core/certificate_charts.py`, `core/certificate_pdf.py`, `core/certificate_text.py`
- `core/showcase.py`, `core/management/commands/seed_showcase.py`
- `core/tests/test_certificate.py`, `core/tests/test_showcase.py`
- `assets/brand/fonts/` (9 static fonts + 3 OFL licences), `tools/build_fonts.py`
- `docs/guides/certificate.md`, `docs/guides/showcase.md`, `certificate_test_output.txt`

**Modified:**
- `core/views.py`, `fruitcam/urls.py` (endpoint)
- `core/stats.py` (`scope()`, the faster identical `rows()`)
- `frontend/src/api.js` (`download`)
- `frontend/src/views/DashboardView.vue` (button; overview row height)
- `frontend/src/charts.js` and `frontend/src/series.js` (cut volume scale)
- `frontend/src/strings.js` (strings)
- `frontend/src/style.css` (one rule)
- `frontend/tests/series.test.mjs` (`robustLimit` test)
- `core/tests/test_dashboard.py` (expects 11 Node tests)
- `requirements.txt`, `frontend/dist/` (rebuilt)
