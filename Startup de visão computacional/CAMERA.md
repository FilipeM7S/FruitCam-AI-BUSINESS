# FruitCam_ai on the conveyor belt: cameras, three-class AI and line statistics

This document explains FruitCam_ai as a system of **fixed cameras on a conveyor belt**: what it does, why each engineering decision was made, what was measured, and where everything lives in the code. It starts with plain concepts and goes down to the code. At the end: test results, sizes, changed files and what was **not** verified.

> **Read this first (2026-10-04, data audit).** The first version of this document reported 80.9% accuracy for the classifier. That number was an artefact. The public dataset we train on numbers its classes in two different ways, and in 1,466 of its 3,098 photos a whole cashew tree is labelled as "spoilt". The old model learned to call tree crops "rotten". On photos with consistent labels, its balanced accuracy was 44% (chance is 33%). We removed those photos, retrained, and re-measured everything. The honest state today: **counting and measuring work; the classifier is weak (balanced accuracy about 50%), so every fruit it classifies goes to manual review.** Real belt images are the way forward; sections 7 and 8 explain how.

Contents

1. [What changed](#1-what-changed)
2. [Concepts in plain words](#2-concepts-in-plain-words)
3. [The data, and what was wrong with it](#3-the-data-and-what-was-wrong-with-it)
4. [The AI: training and honest results](#4-the-ai-training-and-honest-results)
5. [The camera pipeline (`belt/`)](#5-the-camera-pipeline-belt)
6. [Validation on a simulated belt](#6-validation-on-a-simulated-belt)
7. [Real belt data: an industrial potato line](#7-real-belt-data-an-industrial-potato-line)
8. [Collecting your own belt data](#8-collecting-your-own-belt-data)
9. [Server: events, camera worker, line API](#9-server-events-camera-worker-line-api)
10. [The app](#10-the-app)
11. [Running it](#11-running-it)
12. [Figures](#12-figures)
13. [Tests and their real output](#13-tests-and-their-real-output)
14. [Sizes](#14-sizes)
15. [Changed files](#15-changed-files)
16. [What was not verified, and what to do next](#16-what-was-not-verified-and-what-to-do-next)

---

## 1. What changed

| Before | Now |
|---|---|
| A person photographs one fruit and uploads it | A fixed camera films the belt; every fruit that passes is counted once, measured and classified |
| Two classes: `nao_podre` / `podre` | Three classes: **boa**, **baixa qualidade**, **podre**, plus **revisar** when the model is not confident enough |
| Whole-photo classification | Per-fruit classification on crops, averaged over up to 6 frames |
| Statistics per week and sector | Also per minute, per camera/line and per lot: throughput, class shares with 95% intervals, control chart with alarms, lot acceptance |
| Training labels taken at face value | Labels audited: 1,466 photos with a different class numbering are excluded |
| Reported 80.9% accuracy | Re-measured on clean labels: balanced accuracy 53.3% for the deployed model; no confidence level reaches 95% accuracy, so **all** fruit go to review |
| No real belt data | Pipeline and training recipe checked on a real industrial potato line (open data); tools and protocol to record your own belt |
| Light theme (dark optional) | Dark theme only, soft green; background videos and photos; camera explainer on the first page; a “?” user guide on every page |

Photo inspection still exists (page *Inspeção por foto*) for checking single fruits off the line; it uses the same three-class model on the fruit crop.

---

## 2. Concepts in plain words

**Camera over a belt.** An industrial camera fixed above the belt sees fruit move in a straight line at the belt's speed. With constant light and a belt colour that contrasts with the fruit, separating fruit from belt is a colour problem, not an AI problem. Calibration gives *pixels per millimetre* (px/mm), so areas in pixels become sizes in millimetres.

**Segmentation.** Each pixel is compared with the belt colour in the Lab colour space (which separates lightness from colour). Pixels far enough from the belt colour form a mask; small specks are removed; each connected region is one fruit candidate. This only works when fruit and belt differ in colour (section 7 shows a belt where it fails).

**Tracking and the counting line.** A fruit appears in many consecutive frames. The tracker predicts where each fruit will be in the next frame and links detections into one *track*. A fruit is counted exactly once, when its centre crosses a dashed **counting line**.

**Multi-view classification.** The same fruit is seen several times before the line, so the classifier looks at up to 6 crops of it and averages the probabilities.

**Calibrated confidence and review.** Temperature scaling makes the model's stated confidence match its real hit rate (fitted on validation data). A **review threshold** is the lowest confidence at which the model was at least 95% right on validation. Fruit below it goes to **revisar**. If no confidence level reaches 95%, there is no threshold and every fruit goes to review: that is the situation today.

**Balanced accuracy.** The average of the hit rate of each class. When one class dominates (78% of our test crops are "podre"), plain accuracy can look good while the model ignores the rare classes. With three classes, guessing gives a balanced accuracy of 33%.

**Wilson interval, control chart (Laney p′), lot acceptance.** As before: a 95% interval for each share; a control chart whose limits account for normal variation between windows, with the median as the centre and a second rule for 8 windows in a row above the median; and lot verdicts *aprovado* / *reprovado* / *inconclusivo* by comparing the interval of the rotten share with the line's maximum.

**Split by source photo, or by tray.** Crops of the same photo (or fruit from the same tray) are correlated. Test data must come from photos or trays never used in training, or the test looks easier than reality.

**Label audit.** Checking that labels mean what the documentation says. Here a simple check found it: in some files the "spoilt" class boxes cover the whole photo.

**Compositing.** Cutting the fruit out of a field photo (here with OpenCV's GrabCut, seeded by the labelled box) and pasting it on a synthetic belt, so the model sees belt-like backgrounds during training.

**AdaBN.** Re-estimating the network's normalisation statistics on unlabelled images from a new setting (for example your belt). It needs no labels, but it is not guaranteed to help.

---

## 3. The data, and what was wrong with it

### Where it comes from

The project's `images/` and `Labels/` folders are the cashew part of the **Coffee and Cashew Nut Dataset** (Makerere University, Uganda; Nakatumba-Nabende et al., Mendeley Data, [doi:10.17632/r46c6bpfpf.1](https://doi.org/10.17632/r46c6bpfpf.1); paper in *Data in Brief* 52, 2024). Licence: **CC BY 4.0**, which allows commercial use with credit. Evidence that it is the same data: 3,098 photos and exactly 88,364 boxes, matching the published copy, and per-class box counts that match the paper's Table 2 exactly. The credit now appears on the app's Credits page.

The paper defines six classes: 0 tree, 1 flower, 2 premature, 3 unripe, 4 ripe, 5 spoilt. We map ripe → **boa**, premature and unripe → **baixa qualidade**, spoilt → **podre**, and ignore tree and flower.

### The numbering problem

[tools/audit_cashew_labels.py](tools/audit_cashew_labels.py) (output in `docs/datasets/cashew_label_audit/`) splits the label files by one rule: does the file have a class-5 box covering at least 60% of the photo?

| Group | Files | Class 0 boxes (median longer side) | Class 5 boxes (median longer side) |
|---|---|---|---|
| Paper numbering | 1,632 | 1,741 boxes, 99.8% of the photo (trees) | 24,016 boxes, 3.4% (fruit) |
| Different numbering | 1,466 | 3,606 boxes, 13.5% (look like flower panicles) | 1,804 boxes, 99.9% (**trees**) |

In the second group, "tree" is saved as 5. Looking at crops of the other IDs in that group, 2 is probably premature, 3 ripe and 4 spoilt, but a colour-and-size matching against the first group was inconclusive (the best orderings differed by about 5% in cost and contradicted what is visible). We do not guess: **those 1,466 photos are excluded** from training and testing, and the question is in the draft e-mail to the authors ([DATA_REQUESTS.md](DATA_REQUESTS.md)). Excluded files are found by `tree_as_five()` in [train_belt.py](train_belt.py), and a test checks the rule.

Effect on the old model (`belt_v1`, trained on all files): 85% of its test crops came from the misnumbered group, where "rotten" meant "a tree crop" and was recognised 99.6% of the time. Re-scored on the clean photos only, its saved test predictions give 48.5% accuracy and **39.4% balanced accuracy** (boxes ≥ 24 px). The 80.9% was measuring the label error.

### What is left

With boxes of at least 16 px on the short side and the same photo-level split as before (sha256 of the file name, 70/15/15), the clean data is small and unbalanced:

| Split | Photos | boa | baixa qualidade | podre |
|---|---|---|---|---|
| Train | 741 | 330 | 700 | 2,232 |
| Validation | 157 | 84 | 112 | 510 |
| Test | 149 | 56 | 84 | 509 |

The minimum box side was lowered from 24 to 16 px to keep more data; the test results below are also reported for the ≥ 24 px subset.

---

## 4. The AI: training and honest results

### Training ([train_belt.py](train_belt.py))

Same recipe as before: MobileNetV3-Small (ImageNet weights), 128 px input, 14 epochs, AdamW with cosine schedule, class-weighted loss, rotation/flip/brightness/contrast/saturation augmentation without hue shift, checkpoint chosen by validation balanced accuracy, temperature and review threshold fitted on validation, test used once. New options:

- `--paper-numbering-only`: skip the 1,466 misnumbered label files.
- `--composite P`: paste a share P of the training crops (fruit only, cut out with a GrabCut mask seeded by the labelled box) onto a random synthetic belt with shadow, weave texture, light gradient and occasional motion blur ([belt/composite.py](belt/composite.py)). Training belts use six colour families; **blue and light blue are never used in training** and are kept for testing. Masks are cached in `data_cache/fruit_masks.npz`; GrabCut succeeded on 3,214 of 3,262 training crops (the rest use an ellipse).

Two models were trained on the clean data: `belt_v2_clean` (no compositing) and `belt_v2` (compositing on half the crops).

**Deployment rule, fixed before seeing the belt results:** deploy `belt_v2` unless it is worse than `belt_v2_clean` on the held-out blue-belt composites; never redeploy `belt_v1`. Result: `belt_v2` is deployed (it is not worse there), and it is the default in [fruitcam/settings.py](fruitcam/settings.py). To use the other one: `$env:FRUITCAM_MODEL_PATH = "models/belt_v2_clean.pt"`.

### Results on the clean test photos

All models scored by [tools/compare_models.py](tools/compare_models.py) on the same 649 test crops from 149 photos (56 boa, 84 baixa qualidade, 509 podre). Intervals are 95%, bootstrap over photos. Always answering "podre" scores 78.4% plain accuracy, so balanced accuracy is the fair measure (chance: 33%).

| | belt_v1 (old) | belt_v2_clean | **belt_v2 (deployed)** |
|---|---|---|---|
| Accuracy | 43.0% (37.6–48.9) | 63.2% (57.4–68.1) | 54.2% (48.5–59.7) |
| **Balanced accuracy** | 44.2% (36.8–51.8) | 51.5% (45.4–58.1) | **53.3%** (46.0–60.9) |
| Recall boa / baixa / podre | 43% / 48% / 42% | 52% / 33% / 69% | 61% / 44% / 55% |
| Rotten called good | 93 of 509 | **49 of 509 (9.6%)** | 96 of 509 (18.9%) |
| Balanced accuracy, boxes ≥ 24 px (194 crops) | 39.4% | 47.1% | 45.1% |
| Review threshold reaching 95% on validation | 0.81 (but measured on bad labels) | none | none |

`belt_v2` calibration: ECE 0.101 before and 0.044 after temperature scaling (T = 1.61). No confidence level reaches 95% accuracy on validation, so **the deployed model decides nothing on its own: every fruit goes to review**, with the model's suggestion and probabilities. The code treats a missing threshold this way everywhere (`CropClassifier.needs_review`).

What this says:

1. **Cleaning the labels was the real improvement**: 5 to 9 points of balanced accuracy over v1 on every test (field photos, blue-belt composites, simulated belt).
2. **Compositing did not clearly help.** `belt_v2` and `belt_v2_clean` are within each other's intervals everywhere, and `belt_v2` calls twice as many rotten fruit "good" on field photos. The pre-set rule chose `belt_v2`; with every fruit going to review, the practical difference is small.
3. **The public field data cannot produce a usable grader.** About 50% balanced accuracy is far from what a line needs. Belt images labelled by tray (section 8) are needed.

The bug found earlier still stands fixed: inference resizes crops exactly like training (difference below 1e-5, measured 2.4e-7).

---

## 5. The camera pipeline (`belt/`)

Pure Python, independent of Django, so it can run next to a camera on an edge PC.

- [belt/source.py](belt/source.py) `CameraSource`: OpenCV capture of an RTSP/HTTP URL, a USB index or a video file; live sources reconnect.
- [belt/detect.py](belt/detect.py) `BeltDetector`: Lab colour distance to the belt (lightness down-weighted), threshold 14, morphological open/close, connected components, area filter in mm² (250 to 8,000). The belt colour is re-estimated slowly from belt-only pixels.
- [belt/track.py](belt/track.py) `Tracker`: predicts each track at belt speed, counts a track once when its centre crosses the line, keeps up to 6 square crops per track.
- [belt/classify.py](belt/classify.py) `CropClassifier` (calibrated probabilities, training-identical preprocessing, `needs_review`), `ModelDecider` (averages views, review rule, optional size rule), `TruthDecider` (simulation labels, for demos and tests).
- [belt/pipeline.py](belt/pipeline.py) `BeltPipeline`: detect → track → decide at the line, plus the annotated frame.
- [belt/simulate.py](belt/simulate.py) `SimulatedBelt`: procedural fruit, or real crops pasted as discs or with their fruit masks; exact ground truth.
- [belt/stats.py](belt/stats.py): Wilson interval, windows, Laney p′ chart, lot verdicts, summary for the API.
- New: [belt/composite.py](belt/composite.py) (GrabCut masks, synthetic belts, compositing) and [belt/dataset.py](belt/dataset.py) (tray recorder, manifest, split by tray).

---

## 6. Validation on a simulated belt

There is still no labelled cashew belt footage, so the full pipeline was validated in simulation, with exact answers.

**Counting and size.** Every fruit that crossed the line was counted exactly once: 178/178 at 2 fruit/s and 326/326 at 5 fruit/s (procedural fruit), 918/918 with real test crops pasted as discs, and **914/914 with real test fruit pasted with their masks** (no leaves, the realistic case). No double counts in any run. Measured diameters: within a few percent for procedural fruit; median ratio 1.029 (5th–95th percentile 0.979–1.061) for masked real fruit.

A simulator bug was found and fixed on the way: masked fruit were scaled by the crop size, not the fruit size, so they came out 12–17 mm long, below the detector's 250 mm² minimum, and 19% were not counted. The fruit itself now gets the sampled length (32–62 mm, depending on class).

**Classification end to end** ([tools/eval_belt.py](tools/eval_belt.py), figure 8; [tools/compare_models.py](tools/compare_models.py)). The simulated belt carried the same clean test fruit, 1:1:1 by class, for 8 simulated minutes. Balanced accuracy (plain accuracy in brackets):

| | Field photos | Blue belt composites (colour never seen in training) | Simulated belt, masked fruit | Simulated belt, fruit as discs with leaves |
|---|---|---|---|---|
| belt_v1 | 44.2% | 41.1% (28.2%) | 37.9% (38.6%) | 36.8% |
| belt_v2_clean | 51.5% | 46.3% (32.4%) | **47.0%** (47.2%) | 36.7% |
| **belt_v2** | **53.3%** | **47.6%** (41.1%) | 44.0% (44.0%) | 38.4% |
| belt_v1 + AdaBN | — | 34.3% | 31.7% | — |
| belt_v2 + AdaBN | — | 44.8% | 44.1% | — |

AdaBN was adapted on unlabelled crops of **validation** fruit in the same setting, never on test fruit. It did not help any model, and it hurt v1. The `adapt_bn.py` tool is kept because a real belt is a much bigger shift than our synthetic ones, but its effect must be checked on labelled trays before use.

Every number in this section is a synthetic setting built from real fruit images. None is a measurement on a real cashew belt.

---

## 7. Real belt data: an industrial potato line

The only open, commercially usable dataset from a real sorting line we found is the **Potatoes Dataset** (University of Pardubice; Štursa, Doležel, Ksiažek; [Zenodo 17494608](https://zenodo.org/records/17494608), CC BY 4.0): a Basler camera perpendicular to an industrial belt, objects labelled Good, Damaged, Plant or Stone. It is not cashew, but it is real. Everything below comes from [tools/eval_potatoes.py](tools/eval_potatoes.py); results are in `docs/datasets/potatoes/potato_eval.json`.

**What the data really contains.** 4,145 files, all 50×50 px single-object crops, so tracking and counting cannot be tested with it. Only 1,294 are unique pixel for pixel, and only **757 are unique once rotations and flips are counted as copies** (712 groups after merging near-duplicates). **224 of the 288 distinct objects in the official test sets also appear in train or validation**, so results on the official splits are inflated. We used our own split by object group.

**Segmentation by colour fails on this belt.** Using our detector's exact rule, with the belt colour taken from the crop corners (a dark grey-blue):

| Setting | Potato centres separated | Stone centres separated | Belt corners marked as object |
|---|---|---|---|
| Our default (threshold 14, lightness weight 0.5) | 35% | 16% | 47% |
| Threshold 8 | 91% | 81% | 85% |
| Threshold 10, full lightness weight | 95% | 91% | 93% |

At no setting are both numbers good: the potatoes are too close to this belt in colour. (Corners sometimes contain a neighbouring object, so the last column is an upper bound, but not by that much.) For cashew the picture is better: the median colour distance between real cashew fruit and this belt colour is 45 to 57 (threshold 14), with at least 99.9% of crops above the threshold in every class. That is a colour comparison, not a test on a cashew belt. The lesson is to choose a belt colour that contrasts with the fruit, and to keep the full frames from your own recordings so segmentation can be checked or learned.

**Our training recipe on real belt images** (5-fold cross-validation by object group, 757 objects): accuracy **90.6%** (88.5–92.7%) against 74.0% for always answering "Good"; balanced accuracy 84.1%. Good potatoes 97.7%, plants 97.7%, stones 88.4%, but **damaged potatoes only 52.7%**: 52 of 110 were called good. The recipe works on real belt imagery, and rare defect classes are the weak point. That is why the collection protocol asks for many more rotten and poor-quality trays.

---

## 8. Collecting your own belt data

The full procedure, written for whoever runs it, is in [DATA_COLLECTION.md](DATA_COLLECTION.md). In short:

- Sort fruit by hand into trays (boa / baixa qualidade / podre), then run each tray across the belt on its own: `python manage.py record_tray linha-1 --label podre --batch 2026-10-12-podre-A`. Every fruit that crosses the line is saved as up to 6 crops labelled with the tray's class, plus one full frame every 2 s, and a row per crop in `belt_data/manifest.csv`. Nothing is written to the statistics database; a batch name cannot be reused with another label.
- `python tools/finetune_belt.py --data belt_data --init models/belt_v2.pt --mix-field` splits by tray (each class needs at least two trays; with three or more, one is validation), and prints the starting model and the fine-tuned model on the **same held-out trays**.
- `python tools/adapt_bn.py --init models/belt_v2.pt --crops belt_data` makes an AdaBN candidate from unlabelled crops (`--label sem_rotulo`).

Seven ready-to-send requests for more data (the cashew dataset authors about the numbering, FruitRoll-360 for commercial use, Embrapa Agroindústria Tropical, processors with optical sorters, and others) are drafted in [DATA_REQUESTS.md](DATA_REQUESTS.md). Nothing has been sent.

---

## 9. Server: events, camera worker, line API

- **Event model** ([core/models.py](core/models.py), migration `0002_camera_events`): `source`, `camera`, `lot`, `track_id`, `label`, `size_mm`, `needs_review`, `decided_by` (modelo, regra_calibre, simulacao), `model_version`. Fruit pending review is excluded from the weekly analytics ([core/stats.py](core/stats.py)) until someone decides it.
- **Camera configuration** ([config/cameras.json](config/cameras.json)): source, px/mm, counting line, belt rows, minimum size, maximum rotten share for lot acceptance, simulation parameters.
- **Camera worker** ([run_camera](core/management/commands/run_camera.py)): one event per counted fruit; every 0.5 s the annotated frame and a status file. With `sim`, labels come from the simulation unless `--decider model`.
- **Tray recorder** ([record_tray](core/management/commands/record_tray.py)): section 8.
- **Writing the live frame** ([core/cameras.py](core/cameras.py)): on Windows another process (for example OneDrive syncing the folder) can briefly lock `frame.jpg`. The atomic replace now retries a few times and otherwise skips that snapshot, instead of stopping the worker.
- **A locked database no longer stops the worker** (found on 2026-10-05 while taking layout screenshots): with SQLite, opening the dashboard runs seven heavy reads at once, and the worker's insert could fail with `database is locked`; the worker crashed and the live frame went offline. SQLite now runs in WAL mode with a 20 s busy timeout and immediate write transactions ([fruitcam/settings.py](fruitcam/settings.py)), and the worker keeps counted fruit in memory and retries on the next frame, so nothing is lost. A test makes the first three inserts fail and checks that every counted fruit is stored. Reproduced before the fix (crash in the first round of seven parallel dashboard loads), and not after (six rounds, worker alive).
- **Demo data** ([seed_line_demo](core/management/commands/seed_line_demo.py)): 8 h of synthetic traffic with one bad lot.
- **API** ([core/line_views.py](core/line_views.py)): `/api/cameras`, `/api/cameras/<slug>/frame`, `/api/line`. Login required. Responses are cached until the data changes; the key includes the number of events pending review, so deciding a pending fruit refreshes the numbers.
- **Photo inspection** ([core/inference.py](core/inference.py)): the fruit crop is classified; the response carries the three probabilities and the review flag.

---

## 10. The app

- **Dark theme only**, soft green accents, re-themed charts.
- **Layout (reorganised on 2026-10-05, see [docs/dataset_and_layout.md](docs/dataset_and_layout.md))**: one app shell with a top bar and one navigation that is a bottom bar on phones, an icon rail from 1024 px and a sidebar with groups (Operação, Análise, Sobre) from 1280 px; the same page header on every page; layout tokens and a 12-column grid; an axe scan finds no violations.
- **Linha page** (first page after login): a page header over the simulated-belt video; "Linha ao vivo" first, with the live frame, indicators with 95% intervals, flow chart, control chart, lots and median size; "Como a câmera funciona" (six steps and an animated diagram) after it on the same page; a "Dados sintéticos" notice on demo data.
- **Painel**: a sticky bar with period and sector, then the 8 statistics in five sections: Visão geral, Qualidade agora, Tendências, Distribuições, Previsão.
- **User guide behind a big “?”** on every page (also the `?` key), nine sections. The "limits" section now says plainly that the classifier is weak, that every fruit goes to review, and why the old 80.9% was wrong.
- **Como funciona**: the quality section opens with a data-correction paragraph, then the measured numbers (filled from the figure data, so they always match `belt_v2`'s evaluation), the "no reliable threshold, everything to review" statement, and the simulated-belt result.
- **Inspeção por foto**: the analysed photo sits beside the result panel on desktop and above it on phones; the verdict is shown in the review colour with the note "the model does not have enough confidence to decide alone"; with the deployed model this happens for every photo.
- **Credits**: a new section credits the training and evaluation datasets (Makerere cashew dataset, CC BY 4.0, used for training; Pardubice potato dataset, CC BY 4.0, evaluation only).
- **Backgrounds and video**: unchanged design; the demo video was re-recorded with `belt_v2`. For the CC0 cashew photo the model now answers "boa" with 69.4% and sends it to review. (The old model had called the same photo rotten with 81.4% and decided it on its own.)

---

## 11. Running it

```powershell
$env:DJANGO_SECRET_KEY = "any-long-random-string"
$env:DJANGO_HTTPS = "0"
$env:FRUITCAM_DEMO_PASSWORD = "Caju-Demo-2026"
python manage.py migrate
python manage.py seed_demo
python manage.py seed_line_demo
cd frontend; npm run build; cd ..
python manage.py runserver 127.0.0.1:8000
```

In a second terminal (same `DJANGO_SECRET_KEY` and `DJANGO_HTTPS`): `python manage.py run_camera linha-1` for the simulated camera, or `--source rtsp://user:password@camera-ip/stream` for a real one. Log in at http://127.0.0.1:8000 with user `demo`.

Reproducing the numbers in this document:

```powershell
python tools/audit_cashew_labels.py
python train_belt.py --paper-numbering-only --min-side 16 --out models/belt_v2_clean.pt
python train_belt.py --paper-numbering-only --min-side 16 --composite 0.5 --out models/belt_v2.pt
python tools/compare_models.py
python tools/eval_belt.py
python tools/eval_potatoes.py
python figures/make_figures.py
```

`eval_potatoes.py` reads the potato crops that `python scripts/fetch_datasets.py` downloads and extracts into `data/external/potatoes/`.

---

## 12. Figures

Regenerated by [figures/make_figures.py](figures/make_figures.py) from `belt_v2` (set by `MODEL_NAME`), SVG and PNG 300 dpi, data label in the corner:

| # | Title | Data |
|---|---|---|
| 1 | Da câmera à estatística da linha | schematic |
| 2 | Classifier input/output on a CC0 cashew crop: "boa" 0.72 (still sent to review), dark synthetic ellipse "podre" 0.43 | real examples, not a metric |
| 3–5 | Weekly analytics | synthetic |
| 6 | Model quality on the clean test photos: confusion matrix, per-class recall/precision against "always podre", calibration, coverage × accuracy with the statement that no threshold reaches 95% | real measurement (field photos) |
| 7 | Laney p′ control chart and lot acceptance | synthetic |
| 8 | Simulated belt with masked real test fruit: counting 914/914, confusion, accuracy with one and six views, nothing decided automatically | simulation |

Figures 6 and 8 now adapt their axes to low accuracy, and figure 6 names the actual majority class.

---

## 13. Tests and their real output

Run on 2026-10-04 with `belt_v2` as the model (Windows 11, Python 3.13, Edge via Playwright). Full output: [camera_test_output.txt](camera_test_output.txt).

```powershell
$env:DJANGO_SECRET_KEY = "any-long-random-string"; $env:DJANGO_HTTPS = "0"
python manage.py test core -v 2     # Ran 67 tests in 720.164s - OK
python test_fruit_analytics.py      # 64/64 checks passed
```

| Module | Tests | What it proves |
|---|---|---|
| `core/test_belt.py` | 16 | camera pipeline, line statistics, worker, line API, and (new) tray recording, split by tray, fruit masks, misnumbered-label detection |
| `core/tests.py` | 27 | auth, upload, photo inference, weekly statistics, commands |
| `core/test_dashboard.py` | 11 | weekly dashboard against ground truth, incl. the 10 front-end series tests |
| `core/test_media.py` | 13 | media licences, figures, logo, guide, motion, reduced motion, Save-Data, page weight, 360 px layout |

Numbers printed by the tests:

| Test | Result |
|---|---|
| Counting, 2 and 5 fruits/s for 90 s | 178/178 and 326/326 counted, all distinct, 0 unmatched |
| Camera preprocessing vs training transform | largest probability difference 2.4e-7 |
| Model decider with `belt_v2` | temperature 1.606, no review threshold: 74 of 74 fruit sent to review |
| Tray recorder (simulated, 12 s) | 11 fruit, 66 crops, 7 full frames, all labelled `podre`, 0 events in the database; reusing the batch with another label is refused |
| Split by tray | every test tray appears only in the test split; a class with one tray is refused |
| Fruit mask on a synthetic fruit among leaves | GrabCut, IoU 0.998 with the true fruit; composite on a held-out blue belt |
| Misnumbered label files | the file with a whole-photo class-5 box is flagged, the paper-numbered one is not |
| Real/demo separation with review | 2 photos pending review: 0 in the overview before review, 2 after (cache refreshes) |
| Control chart, one lot shifted 14% → 35% | windows 12–17 flagged, exactly the shifted ones |
| False alarms, 60 in-control days × 8 h | 3 of 1,920 windows (0.156%); a 3σ rule expects about 0.13% |
| Wilson interval vs published values | 0/10 → [0, 0.27753]; 5/20 → [0.11186, 0.46870] |
| Save-Data | posters only, 0 video files requested |

Test problems found and fixed in this round:
- `test_saved_row_matches_response` compared the stored "good" flag against the two-class list in `fruit_analytics.py` (`nao_podre` only). It passed before only because `belt_v1` never called the synthetic test image good; `belt_v2` calls it "boa". The test now uses the same good-label set as the server (`boa`, `nao_podre`); `fruit_analytics.py` is untouched.
- `test_model_decider…` assumed a review threshold always exists; it now also covers "no threshold, everything to review".
- From the camera round (still fixed): stale stats cache after a review, network-dependent video tests, the guide's last-section scroll check, the login rate limit across tests, and a reduced-motion probe that caught 0.01 ms transitions.

---

## 14. Sizes

**Models.** `belt_v2.pt` 6,214,231 B; `belt_v2_clean.pt` 6,216,179 B; `belt_v1.pt` 6,214,103 B (kept for comparison; not used by the app). All are MobileNetV3-Small. The fruit-mask cache is 2.5 MB. Time per crop was not benchmarked; the simulated pipeline with simulation labels ran at 13–26 frames/s in tests on a shared laptop CPU.

**Front-end bundle** (Vite 8; raw / Brotli as served):

| Chunk | Raw | Brotli |
|---|---|---|
| `index` (app shell, router, guide dialog) | 51.8 KB | 18.3 KB |
| `index.css` | 40.5 KB | 8.4 KB |
| `strings` (all Portuguese text) | 90.0 KB | 31.8 KB |
| `charts` (Chart.js + theme) | 203.1 KB | 60.3 KB |
| `media` | 14.7 KB | 4.1 KB |
| `LineView` / `UploadView` / `HowItWorksView` / `DashboardView` / `CreditsView` | 13.5 / 10.9 / 20.6 / 24.2 / 20.1 KB | 4.6 / 3.5 / 7.3 / 7.1 / 4.4 KB |

**Videos:** login background (USDA, public domain) 6 s, 960×540, 775 KB WebM / 605 KB MP4; Linha hero (simulated belt) 12 s, 258 KB / 325 KB; demo recording 39.8 s, 1280×720, 1,569 KB / 1,855 KB.

**Page weight** (bytes transferred on a cold load in Edge, measured by the browser test; budgets in [core/test_media.py](core/test_media.py) are the worst case plus about 20–30%):

| Page | 360 px | 1366 px | Budget |
|---|---|---|---|
| `/login` | 715 KB | 715 KB | 900 KB |
| `/` Linha | 445 KB | 445 KB | 550 KB |
| `/inspecao` | 134 KB | 155 KB | 190 KB |
| `/painel` | 170 KB | 170 KB | 210 KB |
| `/como-funciona` | 145 KB | 311 KB | 450 KB |
| `/como-funciona`, scrolled to the end with the demo playing | 1,912 KB | 1,984 KB | 2,300 KB |
| `/creditos` (now with the dataset credits) | 99 KB | 99 KB | 125 KB |

With reduced motion or Save-Data, no video file is requested.

**Local data (not served):** `data/external/` (downloaded datasets, see [docs/dataset_and_layout.md](docs/dataset_and_layout.md)); evaluation results in `docs/datasets/`.

---

## 15. Changed files

**New in the data-audit round**
- Code: `belt/composite.py`, `belt/dataset.py`, `core/management/commands/record_tray.py`, `tools/audit_cashew_labels.py`, `tools/compare_models.py`, `tools/eval_potatoes.py`, `tools/finetune_belt.py`, `tools/adapt_bn.py`
- Models and results: `models/belt_v2.pt`, `models/belt_v2_eval.json`, `models/belt_v2_clean.pt`, `models/belt_v2_clean_eval.json`, `models/train_belt_v2.log`, `models/train_belt_v2_clean.log`, `models/compare_models.json`, `models/compare_models.log`, `models/eval_belt_v2.log`, `models/record_demo.log`, `data_cache/fruit_masks.npz`
- Data: `data/external/potatoes/` (Zenodo zip and extracted crops), results in `docs/datasets/potatoes/` (`potato_eval.json`, `segmentation_sheet.png`, `eval_potatoes.log`, `record.json`) and `docs/datasets/cashew_label_audit/` (`files.csv`, `summary.json`)
- Docs: `DATA_COLLECTION.md`, `DATA_REQUESTS.md`

**Modified in the data-audit round**
- `train_belt.py` (`--paper-numbering-only`, `--composite`, mask cache, data source named, "no threshold" reported as 0% decided, default output `belt_v2.pt`), `belt/classify.py` (`needs_review`), `belt/simulate.py` (masked crops, correct fruit scale), `core/inference.py`, `core/cameras.py` (locked-file retry), `fruitcam/settings.py` (default model `belt_v2.pt`)
- `tools/eval_belt.py` (clean test fruit, masks, `--model`), `tools/fetch_media.py` (public-domain licence URL), `tools/record_demo.py` (review wording), `tools/build_summit_pack.py` (labels and model statements)
- `figures/make_figures.py`, `figures/captions.json`, `figures/data/belt_eval.json`
- `frontend/src/strings.js`, `frontend/src/views/HowItWorksView.vue`, `frontend/src/views/CreditsView.vue`
- `core/test_belt.py` (data-collection, mask and misnumbering tests), `core/tests.py`, `core/test_media.py`
- `MEDIA.md` (superseded numbers flagged), this file
- Regenerated: `frontend/public/figures/`, `frontend/public/media/`, `frontend/src/figures.json`, `frontend/src/media.json`, `frontend/src/licenses.json`, `frontend/dist/`, `media_src/video/`, `summit_pack/`, `media_src/sources.json`

**From the camera round (unchanged since)**: `belt/source.py`, `belt/detect.py`, `belt/track.py`, `belt/pipeline.py`, `belt/stats.py`, `config/cameras.json`, `core/line_views.py` (cache key), `core/migrations/0002_camera_events.py`, `run_camera`, `seed_line_demo`, the Linha page, guide, backgrounds and dark theme.

**Not touched**: `model.pt`, `infer.py`, `train.py`, `fruit_analytics.py`, authentication, `models/belt_v1.pt`.

---

## 16. What was not verified, and what to do next

- **No real cashew belt footage.** Accuracy on a real belt is unknown. Next step: record trays (section 8), at least two per class, then fine-tune and measure on held-out trays.
- **The classifier is weak.** Balanced accuracy about 50% on clean field photos; nothing reaches the 95% review target, so everything goes to review. Do not use it to reject fruit or lots.
- **Misnumbered labels.** The class order in 1,466 of the dataset's files is unconfirmed; the e-mail to the authors is drafted, not sent. If they confirm it, those photos (about half the data) can be added back.
- **Segmentation on a real belt.** Colour separation failed on the potato belt; for cashew it looks favourable by colour but is untested. Check the saved full frames from the first recordings.
- **Touching fruit** become one blob and are counted once.
- **Real cameras.** RTSP/USB capture reconnects, but no physical camera was connected; frame rate on target hardware is unmeasured.
- **Defects.** Only immature and rotten are in the data; bruised, cracked and burnt are not. Castanha and melão have no training images.
- **No review screen yet.** Fruit sent to *revisar* stays out of the weekly analytics until a screen exists to record the decision.
- **Statistics with production data**, **database scale**, **browsers** (Edge on Windows only), **live view bandwidth** and **licensing** (no legal review): as before.
