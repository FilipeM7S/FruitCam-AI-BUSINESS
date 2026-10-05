# Belt datasets and site layout: what was done, why, and how to check it

This task had two parts: **(A)** find, verify and install fruit-on-belt datasets that a startup may use commercially, convert them to our format and measure the current model on them; **(B)** reorganise the web app so it reads as one product. It starts with the simple ideas behind each decision and ends with the code, the tests and what was not verified.

**In one paragraph.** No commercially usable dataset of a tropical fruit on a conveyor belt exists among the sources searched. Three datasets with clear licences are now installed and converted: **Potatoes** (a real industrial sorting line, CC BY 4.0), **Lemons** (a lab rig, MIT) and **FruitNet** (phone photos of six fruits, CC BY 4.0). On the potato and lemon crops, the current cashew model's answers depend heavily on the background: with the lemons' black background swapped for grey, it calls 95% of lemons "boa", whatever their defects. The site now has one shell (top bar, plus a navigation that is a bottom bar on phones, an icon rail on small desktops and a sidebar on large ones), the same page header on every page, and a dashboard grouped into five sections on a 12-column grid. Taking the layout screenshots also exposed a real bug: opening the dashboard could crash the camera worker with "database is locked". That is fixed and tested.

Contents

1. [Simple concepts](#1-simple-concepts)
2. [Step 0: what existed](#2-step-0-what-existed)
3. [Part A: datasets](#3-part-a-datasets)
4. [Part B: layout](#4-part-b-layout)
5. [A bug found on the way](#5-a-bug-found-on-the-way)
6. [The code, file by file](#6-the-code-file-by-file)
7. [Verification: tests and their real output](#7-verification-tests-and-their-real-output)
8. [Changed files](#8-changed-files)
9. [What was not verified](#9-what-was-not-verified)

---

## 1. Simple concepts

**Licence.** Images are someone's work. A licence is the permission to use them, and its conditions. For a startup the question is whether *commercial* use is allowed, and on what conditions:
- **CC0** gives everything away.
- **CC BY 4.0** allows any use, including commercial, if you credit the authors, link the licence and say what you changed.
- **MIT** (a software licence that some datasets also use) allows any use if the copyright and permission notice travel with the data.
- **CC BY-SA** adds share-alike: what you build from the data must carry the same licence.
- **Non-commercial** or **research-only** licences rule out a product.
- **No licence, or contradictory terms** mean you have no permission at all.

A model trained on data you may not use commercially is a legal risk for the company that sells it. That is why the licence check comes first and is enforced by a test.

**Checksum.** A short fingerprint computed from every byte of a file (md5, sha256). If the publisher lists one, recomputing it on your copy proves the file arrived complete and unchanged. A file with a different checksum is a different file.

**Data split and data leakage.** Models are trained on one part of the data (train), tuned on a second (validation) and judged once on a third (test). If the same object shows up in two parts (two photos of the same lemon, or the same potato rotated), the test partly measures memory instead of skill, and the score is inflated. That is leakage. The fix is to split by **physical object or capture session**, never by image, and to check that no near-copies cross the boundary. A **perceptual hash** is a fingerprint of how an image *looks*: near-copies have nearly equal hashes, so comparing hashes finds candidates; a pixel correlation then confirms whether two images really are the same picture.

**Label mapping.** Every dataset names its classes differently. We map them to our three (good / poor / rotten) in one file, with a reason for each entry. When the source does not say whether a defect is minor or rot ("Damaged", "Bad"), we keep a merged label (`poor_or_rotten`) instead of guessing. Inventing labels would make the data look more useful than it is.

**Background sensitivity.** A classifier can learn shortcuts: if all rotten training fruit happened to lie on dark soil, "dark background" becomes a cue for "rotten". Swapping the background while keeping the fruit, and seeing whether the answer changes, measures that dependence.

**Layout grid, breakpoint, design token.**
- A **grid** divides the page into equal columns (here 12 on desktop), so cards line up and their widths come from a few spans instead of ad-hoc numbers.
- A **breakpoint** is a screen width where the layout changes (here 768, 1024 and 1280 px).
- A **design token** is a named value, such as `--space-6: 16px` or `--content-max: 1160px`, defined once and used everywhere, so spacing is consistent and changes in one place.
- An **app shell** is the frame that stays the same on every page: top bar, navigation, footer.
- **Sticky** elements stay on screen while the page scrolls.
- A **skip link** lets keyboard users jump straight to the content.
- **axe** is an automated accessibility checker.

---

## 2. Step 0: what existed

### The format the pipeline expects

There are two pipelines in the project, and the task named the older one.

- **Old two-class pipeline** ([crop_dataset.py](../crop_dataset.py), [train.py](../train.py), [infer.py](../infer.py)). `crop_dataset.py` cuts the YOLO boxes of the cashew photos tightly, with no margin, keeping boxes of at least 96 px. It saves them as JPEG to `out_dir/{train,val}/{podre,nao_podre}/<photo>_<box>.jpg` (classes 5 → podre, 4 → nao_podre). The split is random per crop, so crops of one photo can land in both train and val. `train.py` reads this with torchvision `ImageFolder` (`data_dir/train`, `data_dir/val`), resizes to 224×224, and saves `{"model_state", "classes"}`. `infer.py` resizes one image to 224 and prints the top class.
- **Current three-class pipeline** ([train_belt.py](../train_belt.py), `belt/`). Crops are cut on the fly from the YOLO boxes: square, 15% margin, at least 16 px. There are three classes (boa, baixa_qualidade, podre), the split is by photo, and the model input is 128×128 (PIL bilinear resize, ImageNet normalisation). Recorded belt trays use `belt_data/<batch>/<label>/*.jpg` plus `belt_data/manifest.csv`.

The converted datasets follow the current pipeline: square 128×128 RGB PNGs, the size the current model takes, in an ImageFolder-style layout (`images/<split>/<label>/`, which the old `train.py` can also read) plus a `manifest.csv` with the object and group of every image.

### The frontend before

Six routes: `/login`, `/` (Linha), `/inspecao`, `/painel`, `/como-funciona`, `/creditos`. Navigation was a horizontal top bar, shown only when logged in; Créditos was reachable only from the footer. All styling lived in one global stylesheet (3,302 lines), with colour tokens but a single spacing token. It used 25 different pixel values for spacing, the content width `1160px` written in four places, 18 different grid templates, and breakpoints at 640, 960 and 1024 px. Screenshots of every page at 360, 768 and 1280 px are in [layout/before/](layout/before/), and the full inventory is in [layout/plan.md](layout/plan.md).

### Bundle and tests before

- `npm run build`: 2,115,598 B raw, 735,360 B Brotli ([layout/before/bundle.txt](layout/before/bundle.txt)).
- `python manage.py test core -v 2`: 67 tests, OK ([layout/before/test_output.txt](layout/before/test_output.txt)).
- `python test_fruit_analytics.py`: 64/64.

---

## 3. Part A: datasets

### A1. The candidates, re-verified

| Dataset | Licence as written on the source | Hash check | Decision |
|---|---|---|---|
| Potatoes Dataset, University of Pardubice ([Zenodo 17494608](https://zenodo.org/records/17494608)) | Zenodo licence field `cc-by-4.0`; metadata file inside the zip: "License: CC BY 4.0" | md5 `6e75a6ed…` published and matched | downloaded |
| Lemons quality control dataset, SoftwareMill ([GitHub](https://github.com/softwaremill/lemon-dataset), [Zenodo 3965568](https://doi.org/10.5281/zenodo.3965568), v1.0.0) | README at tag v1.0.0: "MIT License, Copyright (c) 2020 SoftwareMill". **The Zenodo record's licence field says "other-open"**; both are recorded, and MIT is followed | md5 `859dbb37…` published and matched | downloaded |
| FruitNet, Meshram and Patil ([Mendeley v3](https://data.mendeley.com/datasets/b6fftwbr2v/3)) | Mendeley licence field on version 3: "CC BY 4.0" (the same as v2) | sha256 `b84851e0…` published and matched | downloaded (`FruitNetDataset.zip`, 3.25 GB). The second file, a `.rar` of almost the same size, was not downloaded: no RAR extractor is installed, and whether its content equals the zip was not verified |
| FruitRoll-360 | "solely for academic and research purposes. Any commercial use requires prior written permission" | – | recorded only |
| Oranges Classification | none in the visible page text; **the page's embedded schema.org metadata declares CC BY 4.0** | – | recorded only: files behind an IEEE DataPort login |
| Sisfrutos Papaya | "on a non-commercial basis ... expressly prohibited for commercial purposes" | – | recorded only |

The cashew training data (Makerere University, CC BY 4.0) was already in `images/` and `Labels/`. It now has a `SOURCE.md` and a manifest entry too, with a content digest of both folders.

### A2. Extra search

About 25 minutes on Zenodo, Figshare, Hugging Face, GitHub, Roboflow Universe, Mendeley Data and Kaggle. **No new dataset qualified.** The closest candidates were a mango set from Vietnam (licence fine, but setting and labels unstated, RAR only), CAPA apples (licence field CC BY 4.0, but the description requires the university's consent) and FruQ-DB (CC BY 4.0, but built from YouTube frames). The full report with every candidate, link and reason is [datasets/a2_search_report.md](datasets/a2_search_report.md).

### A3. Installation

- `python scripts/fetch_datasets.py` reads [scripts/datasets.json](../scripts/datasets.json), the single place where each dataset's URL, version, licence, attribution and published hash are written.
  - It downloads only from the official link, streaming, and computes md5 and sha256 while writing.
  - It refuses a file whose size or published hash does not match.
  - It records the result in `raw/<file>.verified.json`.
- **Idempotent.** On the next run, a file whose size and modification time match the record is skipped without re-hashing, and the script prints "already present and verified, nothing downloaded". A test checks this.
- **Resumable.** The FruitNet download was cut by the server at 541 MB. The script was changed to resume with an HTTP Range request (the server answered `206 Partial Content`), and the finished file still matched the published sha256.
- **On disk**: `data/external/<id>/raw/` (the archive, untouched), `data/external/<id>/extracted/` and `data/external/<id>/SOURCE.md`. The SOURCE.md holds the URL, DOI, version, authors, download date, the licence with its link and its exact wording, the required attribution, the citation, and the published and computed hashes.
- **Licences manifest**: `tools/build_media.py` now writes a `datasets` list into `frontend/src/licenses.json` from the same `datasets.json`. The Créditos page shows it, with Portuguese "use" and "modifications" text in `strings.js`.
- **`.gitignore`**: everything under `data/` is ignored except `data/label_map.json` and `data/external/*/SOURCE.md`. Checked in a temporary git repository by a test. (This project folder is not a git repository, so nothing was committed.)

### A4. Conversion

`python scripts/convert_external.py` turns each dataset into `data/processed/<set>/images/<split>/<label>/*.png` (128×128 RGB) plus `manifest.csv`. The manifest has one row per image: file, split, label, source label, how the label was derived, object id, group, source file and source size. All label mapping lives in [data/label_map.json](../data/label_map.json), with a reason per entry; the dataset cards are generated from the files on disk.

| Set | Setting | Unit and crop | Mapping (reason in label_map.json) | Split by | Images: train / val / test |
|---|---|---|---|---|---|
| `potatoes` | real industrial belt | the published 50×50 object crops | Good → good; Damaged → poor_or_rotten | near-duplicate group of objects (rotations and flips count as copies) | 467 / 104 / 99 |
| `potatoes_foreign_objects` | same | same | Plant → plant, Stone → stone (ignored for quality, kept as their own set) | same | 63 / 11 / 13 |
| `lemons` | lab rig, black background | whole image (one lemon per image; the annotations are defect regions, not fruit boxes) | worst annotated condition decides: mould, gangrene → rotten; illness, dark_style_remains → poor_or_rotten; blemish → poor; no defect region → good (derived; the healthy and greening flags are not in the v1.0.0 export) | fruit number from the file name (all angles of a fruit together) | 2,126 / 342 / 222 |
| `fruitnet` | phone photos, varied backgrounds | whole image (no boxes; often 2 to 5 fruits) | Good → good; Bad → poor_or_rotten; Mixed → ignored | near-duplicate group (perceptual hash ≤ 6; no session data exists) | 12,854 / 2,734 / 2,864 |

**Duplicates across splits**:
- Exact copies: none in any set.
- Near-copies: candidates are pairs with a perceptual-hash distance of 6 or less; a pair is confirmed only if the two 128 px images correlate at 0.99 or more.
  - Potatoes: 0 candidates.
  - Lemons: 9,007 candidates, but the closest pair correlates at only 0.976 (different lemons photographed the same way), so 0 confirmed.
  - FruitNet: 13 candidates, highest 0.972, 0 confirmed.

The cards record what to watch:
- Potatoes: [potatoes.md](datasets/potatoes.md). 757 distinct objects among 4,145 files, and leaky official splits.
- Lemons: [lemons.md](datasets/lemons.md). Only 35 fruit numbers, so validation and test hold 3 fruits each, and the test split has 2 good photos; use cross-validation by fruit.
- FruitNet: [fruitnet.md](datasets/fruitnet.md). Good pomegranate is five times larger than every other class, and 564 full-resolution originals are mixed into the processed set.

### A5. Background sensitivity of the current model

The current model (`belt_v2`, unchanged) classified every converted potato and lemon crop twice: as published, and with the background set to grey by the segmentation rule the camera pipeline already uses. That rule is Lab colour distance to the background, threshold 14, with the same morphology; the background colour is taken from each crop's border. Full tables with confusion matrices: [datasets/a5_background_sensitivity.md](datasets/a5_background_sensitivity.md).

**These numbers measure how much the model's output depends on the background. They are not cashew accuracy and not product accuracy.** The model was trained only on cashew field photos, and in the product it sends every fruit to review.

| Set, true label (n) | As published: share counted correct | Grey background | Counted as correct |
|---|---|---|---|
| Potatoes, good (560) | 4.1% | 0.4% | boa |
| Potatoes, poor_or_rotten (110) | 87.3% | 97.3% | baixa_qualidade or podre |
| Lemons, good (124) | 45.2% | **95.2%** | boa |
| Lemons, poor (470) | 45.5% | **2.3%** | baixa_qualidade |
| Lemons, rotten (684) | 25.3% | **3.9%** | podre |
| Lemons, poor_or_rotten (1,412) | 65.9% | **7.4%** | baixa_qualidade or podre |

Masking changed the predicted class for 33.4% of potato crops and **57.2% of lemon crops**.

- **Lemons**: the mask cuts each lemon out cleanly (see `a5_mask_examples_lemons.png`), so this is a clean background swap. With a grey background, the model calls almost every lemon "boa", whatever its defects. Its output depends more on the background than on the fruit.
- **Potatoes**: the mask is poor on this grey-blue belt. It cuts holes into the potatoes, the same colour-segmentation failure measured in CAMERA.md section 7. So the potato grey-background numbers mix background removal with damage to the fruit image. As published, the model calls almost every potato "not good".

What follows for the product: the model must be retrained on images from the actual belt, and background variation (or masking) belongs in training. The tray protocol in DATA_COLLECTION.md is the way to get those images.

---

## 4. Part B: layout

The plan written before implementation is [layout/plan.md](layout/plan.md). Screenshots after: [layout/after/](layout/after/) (every page at 360, 768 and 1280 px, plus the inspection result).

**Information architecture.** One product, three jobs: operate (Linha, Inspeção por foto), analyse (Painel), understand (Como funciona, Créditos). The navigation groups pages exactly that way. Créditos is now in the navigation, and logged-out visitors of the public pages get a top bar with "Entrar". Pages for features that do not exist were not created; the plan lists them as future pages (review screen, tray recording, camera configuration, report export).

**Shell.** Skip link, then the top bar (logo, user and "Sair"), then **one** `<nav>` element, then main, then footer. The navigation's form depends on the width:
- under 1024 px: a bottom bar with five icons and short labels;
- 1024 to 1279 px: an 88 px icon rail;
- from 1280 px: a 232 px sidebar with group labels (Operação, Análise, Sobre).

The active page is marked with `aria-current="page"` and a highlight. The "?" guide button sits above the bottom bar on phones.

**Tokens** (all in `:root` of [style.css](../frontend/src/style.css)):
- Spacing `--space-1` … `--space-11` = 2, 4, 6, 8, 12, 16, 20, 24, 32, 48, 64 px, plus `--hairline` (1 px).
- Widths: `--content-max` (1160 px), `--form-max` (400 px), `--thumb` (88 px).
- Shell sizes: `--topbar-h`, `--bottombar-h`, `--rail-w`, `--sidebar-w`, `--nav-w`.
- Layout: `--page-x` (16, 24 or 32 px by width), `--card-pad`, `--gap`, `--section-gap`, `--cols`.

All 247 spacing declarations were converted. Off-scale values rounded to the nearest step, ties upward (10→12, 14→16, 18→20, 22→24, 28→32), so some paddings moved by 2 px; 40 px became 48 px. Breakpoints were reduced to 768, 1024 and 1280 px (640 → 768, 960 → 1024).

**Grid.** `--cols` is 4 on phones, 8 from 768 px and 12 from 1024 px. Cards take a span by chart type:
- `span-full`: wide time series and per-sector multiples.
- `span-half`: paired charts, 6 of 12 from 1024 px.
- `span-main` + `span-side`: 8 + 4 from 1280 px.

**Page header pattern**, on every page: title, one-line description, actions on the right (below the text on phones). The banner pages keep their illustrative image and credit.

**Pages.**
- **Linha**: the header with the belt video and the "Como a câmera funciona" action; then the live monitor; then the camera explainer, still on this first page.
- **Inspeção**: the photo card holds the setup, the photo, and the annotated result image after analysis; the result panel sits beside it on desktop and below it on phones.
- **Painel**: a sticky bar with period and sector, a second row with dates and data source, then five sections:
  - Visão geral: overview;
  - Qualidade agora: defect 8 + fruit 4;
  - Tendências: good and rotten growth side by side, then the recurring chart;
  - Distribuições: Gaussian and Q-Q;
  - Previsão: forecast.
- **Como funciona** and **Créditos**: the same header and section pattern; Créditos lists the datasets from the manifest.

**Unchanged**: chart code and math, honesty states (insufficient data, n/a, poor fit, demo data, n badges, "Dados sintéticos"), animations and reduced motion, colours and the Okabe-Ito palette, the brand. No framework was added. The only new package is `axe-core`, a development dependency used by the test, not shipped in the bundle.

**Accessibility fixes found by axe**:
- the two hidden file inputs on Inspeção had no label (critical);
- the recurring-chart switch gave radio buttons a `tab` role (minor).

Both are fixed; axe now reports no violations of any impact on all six pages at 360 and 1280 px.

**Bundle**: before 2,115,598 B raw / 735,360 B Brotli; after 2,128,469 B / 737,849 B (+12,871 B raw, +2,489 B Brotli; the stylesheet grew from 40.5 to 45.5 KB raw for the shell and grid).

**Demo video and Summit pack** were re-recorded and rebuilt so they show the new layout. The demo now follows the page order: monitor first, camera explainer after.

---

## 5. A bug found on the way

The first layout screenshots showed the live camera "disconnected" at 1280 px, and so did the screenshots taken **before** any layout change, so it was not caused by the layout. Reproduced: with SQLite, opening the dashboard runs seven heavy statistics reads at once, the camera worker's insert fails with `database is locked`, and the worker crashed (traceback captured).

The fix has two parts:
- SQLite now runs in WAL mode with a 20 s busy timeout and immediate write transactions, so reads stop blocking the worker's writes.
- The worker keeps counted fruit in memory when the database is busy, retries on the next frame, and writes whatever is left before it exits.

After the fix, six rounds of seven parallel dashboard loads left the worker alive, and the final screenshots show the camera online at every width. A test makes the first three inserts fail and checks that every counted fruit is stored.

---

## 6. The code, file by file

**Datasets**
- [scripts/datasets.json](../scripts/datasets.json): metadata of every dataset (URL, DOI, version, authors, licence and its exact wording, attribution, citation, published hashes), plus the three datasets recorded but not downloaded.
- [scripts/fetch_datasets.py](../scripts/fetch_datasets.py):
  - `download()` streams with md5 and sha256, resumes with HTTP Range and retries up to 20 times;
  - `fetch_file()` skips a verified file or re-verifies an existing one;
  - `extract()` unpacks zips, including the zip inside the lemon archive;
  - `local_digest()` hashes the cashew folders;
  - `source_md()` writes SOURCE.md.
- [scripts/convert_external.py](../scripts/convert_external.py):
  - `potatoes()` reuses `tools/eval_potatoes.load()` to group rotated, flipped and near-identical crops;
  - `lemons()` reads the COCO file, applies the worst-region rule and groups by fruit number;
  - `fruitnet()` parses the folders, hashes every photo and groups near-duplicates;
  - `split_of()` hashes the group id (70/15/15);
  - `phash()` and `near_pairs()` (64-bit XOR plus a bit-count lookup) find near-duplicate candidates;
  - `duplicates()` confirms them by correlation, loading images on demand;
  - `card()` writes the dataset cards from the rows on disk.
- [scripts/measure_external.py](../scripts/measure_external.py): A5. `mask_of()` applies the pipeline's `BeltDetector` with the background colour taken from the crop border; `predict()` runs `CropClassifier`; `scores()` builds the confusion matrix and the rates; it writes the JSON, the Markdown report and the example sheets.
- [data/label_map.json](../data/label_map.json): vocabulary, the pipeline class names, foreign-object labels, and per dataset every source class with its target and reason.
- [tools/build_media.py](../tools/build_media.py): adds `datasets` to `licenses.json`.
- [tools/eval_potatoes.py](../tools/eval_potatoes.py), [tools/audit_cashew_labels.py](../tools/audit_cashew_labels.py): paths moved from `data_external/` to `data/external/` (input) and `docs/datasets/` (results).

**Layout**
- [frontend/src/style.css](../frontend/src/style.css): tokens on `:root`; the shell (`.topbar`, `.nav` in three forms, `.nav-group`, `.shell` offsets); `.page`, `.page-head`, `.page-head-text`, `.page-head-actions`, `.section`, `.section-head`; `.grid-12`/`.cards` with spans; `.filter-bar` (sticky) and `.filter-more`; the `.analyze-grid` columns; the `.hero` banner; spacing converted to tokens; breakpoints at 768, 1024 and 1280 px.
- [frontend/src/App.vue](../frontend/src/App.vue): the shell. A `NAV` list of three groups and five links, each with an icon, a long label and a short label; the top bar also on public pages when logged out.
- [frontend/src/components/StatCard.vue](../frontend/src/components/StatCard.vue): a `span` prop replaces `wide`.
- [frontend/src/views/DashboardView.vue](../frontend/src/views/DashboardView.vue): the header pattern, the sticky filter bar plus a second row, and five labelled sections.
- [frontend/src/views/UploadView.vue](../frontend/src/views/UploadView.vue): the annotated image moved into the photo card; labelled file inputs.
- [frontend/src/views/LineView.vue](../frontend/src/views/LineView.vue): the banner header, monitor first, camera explainer after.
- [frontend/src/views/HowItWorksView.vue](../frontend/src/views/HowItWorksView.vue), [CreditsView.vue](../frontend/src/views/CreditsView.vue): the header and section pattern; datasets from the manifest.
- [frontend/src/strings.js](../frontend/src/strings.js): navigation groups and short labels, "Entrar", the Linha header, the dashboard section titles and descriptions, and the dataset use texts.
- [scripts/layout_screenshots.py](../scripts/layout_screenshots.py): starts a throwaway server with demo data and the simulated camera, logs in, and saves full-page screenshots at three widths. It scrolls first, because charts are created only when they become visible, waits for the camera to be online, and prints a diagnosis if it is not.

**Worker**
- [core/management/commands/run_camera.py](../core/management/commands/run_camera.py): pending fruit kept in memory and retried; a summary of how often the database was busy.
- [fruitcam/settings.py](../fruitcam/settings.py): SQLite `timeout`, `transaction_mode` and WAL.

**Tests**
- [core/test_datasets.py](../core/test_datasets.py): 10 tests.
- [core/test_layout.py](../core/test_layout.py): 11 tests.
- [core/test_belt.py](../core/test_belt.py): one new worker test.

---

## 7. Verification: tests and their real output

Full run: [dataset_layout_test_output.txt](../dataset_layout_test_output.txt) (FULL_RESULT). Module runs with the printed numbers: [datasets/test_datasets_run.txt](datasets/test_datasets_run.txt), [layout/test_layout_run3.txt](layout/test_layout_run3.txt).

```powershell
$env:DJANGO_SECRET_KEY = "any-long-random-string"; $env:DJANGO_HTTPS = "0"
python manage.py test core -v 2
python manage.py test core.test_datasets core.test_layout -v 2
python test_fruit_analytics.py
```

### Datasets (`core/test_datasets.py`, 10 tests)

| Claim | Test | Real output |
|---|---|---|
| Hashes match the published ones | recomputes md5/sha256 of each archive on disk | potatoes md5 6e75a6ed… = published; lemons md5 859dbb37… = published; fruitnet sha256 b84851e0… = published; sizes equal |
| Second fetch downloads nothing | runs `fetch_datasets.py`, compares file times before and after | every dataset "already present and verified, nothing downloaded"; "total downloaded: 0 B"; no file touched |
| Every processed image opens with the expected size | opens every file in every manifest | potatoes 670, foreign objects 87, lemons 2,690, fruitnet 18,452: all 128×128 RGB, manifest rows = PNG files |
| Every label is in label_map.json, and follows it | recomputes each label from its source label with the map | 0 rows disagree; labels on disk ⊂ vocabulary |
| No object or fruit in two splits | groups, object ids and lemon fruit numbers per split | 0 groups and 0 objects in two splits in every set; 35 lemon fruit numbers, each in exactly one split |
| Duplicate check across splits | reads the conversion report | exact 0 everywhere; confirmed near-duplicates 0 (candidates: potatoes 0, lemons 9,007 with highest correlation 0.9755, fruitnet 13 with 0.9723) |
| Card counts = disk counts | parses the card tables, counts PNG files per split and label | equal for all four sets (87, 2,690, 18,452 and the 670 potato crops) |
| Every dataset has SOURCE.md and a manifest entry | folders in `data/external` vs SOURCE.md, `datasets.json` and `licenses.json` | potatoes CC BY 4.0, lemons MIT, fruitnet CC BY 4.0, cashew_makerere CC BY 4.0: SOURCE.md present with licence and attribution, all in licenses.json |
| No non-commercial or unclear dataset on disk | licences on disk ⊂ {CC0, CC BY 4.0, MIT, Apache 2.0, CC BY-SA 4.0}; no file named after an excluded set | passes |
| `.gitignore` keeps data out, SOURCE files in | `git check-ignore` in a temporary repository | label_map.json and SOURCE.md not ignored; archives, extracted files, processed images, manifests and reports ignored |

### Layout (`core/test_layout.py`, 11 tests)

| Claim | Real output |
|---|---|
| Spacing and widths come from tokens | spacing scale [2, 4, 6, 8, 12, 16, 20, 24, 32, 48, 64]; 0 spacing declarations with raw px; 0 fixed px max-widths; `.page`, `.card`, `.cards`, `.grid-12`, `.section` use the tokens |
| Only the four breakpoints | min-width breakpoints [768, 1024, 1280]; other media queries: print, prefers-reduced-motion |
| Screenshots exist for every page and width | 21 of 21 in docs/layout/after, widths 360, 768, 1280 |
| No horizontal overflow | scrollWidth = clientWidth on all 6 pages at 360, 768 and 1280 px |
| Every route reachable from the navigation | at 360 px (bottom bar, 360×64 at the bottom), 1024 px (rail, 88 px wide) and 1280 px (sidebar, 232 px, groups Operação, Análise, Sobre): each of the 5 links opens its page (title checked), carries `aria-current="page"` and is in view |
| Skip link and visible focus order | Tab: skip link → logo → Sair → Linha, Inspeção por foto, Painel, Como funciona, Créditos e licenças, every one with a 3 px focus outline and `:focus-visible`; Enter on the skip link focuses `#main` |
| Every statistic renders its chart and its honesty states | at 1280 and 360 px all 8 statistics in their sections, each with at least one drawn canvas, the demo tag, n badges; empty states and warning badges kept (gaussian 2 empty + 3 warnings, forecast 2 + 2, recurring 1); paired cards side by side at 1280 px (deformity 264–915 and fruits 931–1248; growth 264–748 and 764–1248), stacked at 360 px; filter bar stays at 68 px from the top after scrolling 2,400 px, the second filter row scrolls away |
| Inspection result beside the image on desktop, below on mobile | 1280 px: image x 289–804, result panel x 845–1248 (beside); 360 px: image y 816–1013, result panel from y 1254 (below) |
| Page header pattern | on all 5 logged-in pages at 360 and 1280 px: first header in main, with h1 and one-line lead; actions on the right at 1280 px, below the text at 360 px |
| axe finds no serious or critical issues | axe 4.13.0: "violations: none" on all 6 pages at 1280 and 360 px (after fixing 2 unlabelled file inputs and 3 radio roles) |
| Reduced motion still disables animations | 0 running animations and 0 video elements on every page |

### Existing suite and the rest

- `core/tests.py` (27), `core/test_dashboard.py` (11, including the 10 front-end series tests run by `node --test`), `core/test_media.py` (13) and `core/test_belt.py` (17, one new: "linha-1 … database busy 3 times, nothing lost"; bulk_create calls 18, first 3 raised "database is locked"; fruits counted 15, events stored 15).
- One existing test needed a change: `test_every_statistic_is_only_charts` asserted the old order of the dashboard cards (overview last). The new order (overview first, cards grouped by section) is the documented layout, so the expected order was updated to it; the rest of that test (only charts, no tables, labelled frames, lazy rendering) is unchanged and passes.
- `python test_fruit_analytics.py`: ANALYTICS_RESULT.
- Build: `npm run build` passes; bundle 2,115,598 → 2,128,469 B raw, 735,360 → 737,849 B Brotli.

---

## 8. Changed files

**Created**
- Scripts: `scripts/datasets.json`, `scripts/fetch_datasets.py`, `scripts/convert_external.py`, `scripts/measure_external.py`, `scripts/layout_screenshots.py`
- Data (ignored by git except the label map and the SOURCE files): `data/label_map.json`, `data/external/{potatoes,lemons,fruitnet,cashew_makerere}/SOURCE.md`, `data/external/*/raw/`, `data/external/*/extracted/`, `data/processed/{potatoes,potatoes_foreign_objects,lemons,fruitnet}/`, `data/processed/conversion_report.json`
- Docs: `docs/dataset_and_layout.md`, `docs/datasets/README.md`, `docs/datasets/a2_search_report.md`, `docs/datasets/{potatoes,lemons,fruitnet}.md`, `docs/datasets/a5_background_sensitivity.md`, `docs/datasets/a5_measurement.json`, `docs/datasets/a5_mask_examples_{potatoes,lemons}.png`, `docs/datasets/test_datasets_run.txt`, `docs/layout/plan.md`, `docs/layout/before/` (21 screenshots, `bundle.txt`, `test_output.txt`), `docs/layout/after/` (21 screenshots, `bundle.txt`), `docs/layout/test_layout_run*.txt`
- Tests: `core/test_datasets.py`, `core/test_layout.py`, `dataset_layout_test_output.txt`
- `.gitignore`

**Changed**
- Frontend: `frontend/src/style.css`, `App.vue`, `strings.js`, `components/StatCard.vue`, `views/DashboardView.vue`, `views/UploadView.vue`, `views/LineView.vue`, `views/HowItWorksView.vue`, `views/CreditsView.vue`, `frontend/package.json` and `package-lock.json` (`axe-core` dev dependency), `frontend/src/licenses.json` (regenerated, now with `datasets`)
- Server: `core/management/commands/run_camera.py`, `fruitcam/settings.py`
- Tools: `tools/build_media.py`, `tools/eval_potatoes.py`, `tools/audit_cashew_labels.py`, `tools/record_demo.py` (demo order), `tools/build_summit_pack.py` (storyboard order)
- Tests: `core/test_belt.py` (worker test)
- Docs: `CAMERA.md` (worker fix, layout, paths), `DATA_REQUESTS.md` (paths)
- Moved: `data_external/potatoes/dataset_potatoes.zip` → `data/external/potatoes/raw/`; the potato evaluation results and the cashew label audit → `docs/datasets/`
- Regenerated: `frontend/dist/`, `frontend/public/media/`, `media_src/video/` (demo re-recorded), `summit_pack/`, `test_fruit_analytics_output.txt`

**Not changed**: the models and model code (`train.py`, `infer.py`, `train_belt.py`, `belt/classify.py`), the analytics math (`fruit_analytics.py`, `core/stats.py`, `charts.js`, `series.js`).

---

## 9. What was not verified

- **Real phones and other browsers.** Every browser check ran in Microsoft Edge (Chromium) through Playwright at emulated widths of 360, 768, 1024 and 1280 px; no real phone, Safari or Firefox.
- **Screen readers.** axe is an automated scan; no session with a real screen reader.
- **A5 as cashew accuracy.** The A5 numbers measure background sensitivity on potatoes and lemons. They say nothing about how well the model grades cashew on a belt.
- **The FruitNet `.rar` file.** Not downloaded; whether it differs from the zip is unknown.
- **The lemon licence.** The README says MIT, the Zenodo record says "other-open"; no lawyer looked at either. The same goes for every licence here: they were read and recorded exactly, not legally reviewed.
- **The Oranges Classification licence.** CC BY 4.0 appears only in the page's hidden metadata; files need an IEEE DataPort login; not downloaded.
- **Lemon file-name codes.** Two letters in the names are undocumented. Grouping by fruit number alone is conservative but may merge different lemons.
- **FruitNet splits.** There is no capture-session information. Grouping by near-duplicate photos removes repeated shots, but cannot guarantee that two different photos of the same fruit end up in the same split.
- **The camera worker under a real camera and a real database load.** The lock fix was reproduced and tested with SQLite on this laptop only.
