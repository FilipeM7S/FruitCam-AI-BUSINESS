# A2: extra search for fruit-on-belt datasets

**Result: no new dataset qualified.** No commercially usable dataset of a tropical fruit (cashew, mango, guava, melon, papaya, acerola, passion fruit) on a conveyor belt or sorting line, with quality labels, was found. The only real-belt quality dataset with a usable licence remains the Potatoes Dataset (University of Pardubice, CC BY 4.0), already in use.

## How the search was done

- Time box: about 25 minutes on 2026-10-05 (13:18 to 13:43), within the 30 allowed.
- Zenodo, Figshare and Hugging Face through their public search APIs, and GitHub repository search, with 15 queries: fruit conveyor belt, fruit sorting line, fruit quality conveyor, cashew apple quality, mango conveyor, mango defect, guava quality, papaya conveyor, melon quality, passion fruit quality, acerola, citrus sorting line, apple sorting conveyor, tomato sorting conveyor, fruit grading machine vision.
- Roboflow Universe, Mendeley Data and Kaggle through web search (their search pages need JavaScript or an account).
- Zenodo, Hugging Face and GitHub candidates were opened on their own pages (or read through the site API) before deciding. Roboflow Universe and Kaggle results were judged from their search titles and snippets only, because those pages need JavaScript or an account; they are marked below.

Acceptance rule (from the task): page exists; licence explicitly stated on the page and one of CC0, CC BY 4.0, MIT or Apache 2.0 (CC BY-SA only with the share-alike obligation flagged); created by the uploader, not a re-upload and not built from scraped web or YouTube media; a checksum or a stable versioned source.

## Candidates checked and rejected

| Candidate | Link | Why rejected |
|---|---|---|
| CAPA Apple Quality Grading Multi-Spectral Image Database | https://zenodo.org/records/1313615 | Licence field says CC BY 4.0, but the description says it "can be used for academic or research purposes" and "cannot be used without the consent of the ULG (Gembloux Agro-Bio Tech)". Contradictory terms count as unclear. |
| Fruit Quality – Good vs Bad for Apple, Banana, Lime | https://zenodo.org/records/17609211 | The page says it "is derived from the FruitNet dataset": a re-upload. FruitNet itself was downloaded instead. |
| VIC02 (macaúba fruit, Minas Gerais) | https://zenodo.org/records/19128425 | Created by the uploader, CC BY 4.0, Brazilian fruit, but only ripe fruit photographed after collection: no quality labels and no belt. |
| Raw Data of Mangoes; Computer Code (two records) | https://zenodo.org/records/6383935, https://zenodo.org/records/6386398 | CC BY 4.0 and created by the uploaders (Vietnam), but the page states neither the setting (belt or not) nor the quality classes, and the data are RAR archives that could not be opened here. Not accepted; worth a second look with a RAR extractor. |
| Modelos de Inteligencia artificial para la detección de la madurez del mango | https://zenodo.org/records/14783714 | A literature-review spreadsheet, not images. |
| Improvement of the sorting process using a computer vision system and a light sensor | https://zenodo.org/records/19374386 | A journal article (PDF), no data. |
| Fruit Quality Datasets (FruQ-DB) | https://zenodo.org/records/7224690 | CC BY 4.0 on Zenodo, but built from frames of third-party YouTube time-lapse videos: excluded as scraped media. |
| Project-AgML/banana_guava_quality_classification | https://huggingface.co/datasets/Project-AgML/banana_guava_quality_classification | A reformatted copy of another group's dataset (AgML collection): a re-upload. |
| Lemon Quality Inspection Data Set (lonlonago) | https://github.com/lonlonago/Lemon-Quality-Inspection-Data-Set | No licence in the README or the repository; origin not stated. |
| Conveyor Belt (Onkar) on Roboflow Universe | https://universe.roboflow.com/onkar/conveyor-belt | Judged from the search snippet (the page needs JavaScript): "good-and-defective-parts images", industrial parts, not fruit. |
| Kaggle fresh/rotten fruit sets (for example "Scrapped Image Dataset of Fresh and Rotten Fruits", "Fruits fresh and rotten for classification") | https://www.kaggle.com/datasets/swoyam2609/scrapped-image-dataset-of-fresh-and-rotten-fruits, https://www.kaggle.com/datasets/sriramr/fruits-fresh-and-rotten-for-classification | Judged from search titles and snippets (pages need an account): web-scraped images (the first is named "Scrapped Image Dataset") or no stated provenance; not belt imagery. |
| Mendeley mango datasets (MangoLeafBD, MLD24, Mango Leaf Disease) | https://data.mendeley.com/datasets/hxsnvwty3r/1, https://data.mendeley.com/datasets/6dvpywm2m2/1 | Leaves, not fruit quality; not belt. |
| Classification and Quantification of Strawberry Fruit Shape | https://zenodo.org/records/3764216 | Fruit shape, not quality; not belt. |
| CashewTruck (GitHub) | https://github.com/hnguyen154/CashewTruck | Empty repository. |

## Known candidates recorded but not downloaded (A1)

| Dataset | Link | Licence as written on the page | Why not downloaded |
|---|---|---|---|
| FruitRoll-360 (citrus, live factory line, sound / substandard / rotten) | https://ieee-dataport.org/documents/fruitroll-360 | Terms of Use: "This dataset is released solely for academic and research purposes. Any commercial use requires prior written permission from the authors. Users must not redistribute the dataset or any subset thereof without authorization." | Research only; IEEE DataPort login required. Commercial-use request drafted in docs/data/requests.md. |
| Oranges Classification (packing-house conveyor, fresh / rotten) | https://ieee-dataport.org/documents/oranges-classification | No licence in the visible page text. The page's embedded schema.org metadata declares `"license": "https://creativecommons.org/licenses/by/4.0/"`. | Files behind an IEEE DataPort login/subscription, which this task excludes; the CC BY 4.0 appears only in machine-readable metadata, so it should be confirmed with the author. |
| Sisfrutos Papaya | https://github.com/jhony2507/Sisfrutos-Papaya | README, "License to use and download": "... on a non-commercial basis. The use of this dataset, in whole or in part, is expressly prohibited for commercial purposes." | Explicitly non-commercial; links only on request. |

---

# Second search (2026-10-11): real camera footage of fruit, and the original cashew photos

**Result.** No open-licence video of fruit filmed by a fixed camera over a belt, with quality labels, was found; a 2026 paper on apple sorting says the same about public conveyor videos. What the search did find:

1. **The original, full-resolution cashew photos**, with a second country (Ghana) and labels whose class order can be checked against published counts. This is the most useful find and it is now the training data of `belt_v3`.
2. **Unlabelled public-domain footage of real sorting and packing lines** (seed potatoes, citrus) and one share-alike clip of an apple grader. Hand-held camera, people in frame, dense produce. Not usable to teach fruit quality; used only as real backgrounds.

## How the search was done

- Web search (4 queries) for conveyor video datasets, cashew on belts and public-domain packing-line video.
- DataCite index (16 queries; it covers Zenodo, Mendeley Data, Figshare, IEEE DataPort and university repositories).
- Hugging Face dataset search (15 queries), Zenodo search (3 queries), GitHub repository search, Crossref and OpenAlex for one paper.
- Wikimedia Commons file search restricted to video (49 queries, two passes because of rate limits), then the full metadata of 12 candidate files.
- Each accepted source was opened through its own API: licence field, author, dates, file sizes and checksums. Pages that refused automated access (ScienceDirect, Roboflow Universe, PMC) are marked as not verified.

## Accepted

| Source | Licence as written | How the files were checked | Use |
|---|---|---|---|
| Drone-based Agricultural Dataset for Crop Yield Estimation, cashew parts (KaraAgro AI Foundation and the Uganda teams; Hugging Face, doi:10.57967/hf/0959) | Card metadata: `license: cc-by-4.0` | Archives are 4.3 GB and 11.1 GB and the line here gives about 0.5 MB/s, so they were read by HTTP range requests at a pinned revision: every label file of both archives and 1,712 of the 4,715 Ghana photos. Each file matches the size and CRC-32 in the archive's own index. The published SHA-256 of the whole archives was **not** checked, because the archives were not downloaded in full. The small datasheet PDF was downloaded whole and its SHA-256 matches. | Training, validation and test of `belt_v3` |
| 11 clips of sorting and packing lines from the USDA Flickr stream, as copied to Wikimedia Commons | Each file page: public domain, category PD USDA, no restrictions field. The Commons review of the Flickr licence was still pending on 2026-10-11 | Downloaded whole; SHA-1 of every file equals the value published by the Commons API | Real backgrounds: potato clips in training, citrus clip in testing |
| Apple grading and packing (Commons user Amanpanta1990) | File page: CC BY-SA 4.0, own work | Downloaded whole; SHA-1 matches | Testing only, never training (share-alike) |

Content check of the videos, frame by frame on contact sheets: the citrus video is 60 s of drone shots outside the building and then wide shots inside with workers and one inspector; the potato clips are outdoor loading and sorting with workers; the apple clip shows the grader with workers at the side. Faces are visible in several clips, so only regions with produce and belt were cut out, and nothing from these clips is shown on the site (the potato compilation used on the login page was already registered as media).

## What the Ghana labels proved about the Uganda labels

The Uganda label files use two class orders. 1,440 files have the tree as class 5 and had been left out of training because their order was unknown. The Ghana files have the same structure, and their published per-class counts match the files only when the ids are read in alphabetical order of the class names:

| id | boxes in the Ghana files | class in the published card with that count |
|---|---|---|
| 0 | 16,757 | flower |
| 1 | 11,766 | immature |
| 2 | 4,244 | mature |
| 3 | 11,721 | ripe |
| 4 | 518 | spoilt |
| 5 | 1,107 | cashew_tree |

So that batch is `flower, immature, mature, ripe, spoilt, tree`. A look at crops per id agrees (id 3 is red and yellow ripe apples; id 4 is rotten fruit). The other 1,589 Uganda files follow the order printed in the paper (`tree, flower, premature, unripe, ripe, spoilt`). 69 files have no usable tree box and stay out. The paper's Table 2 simply counts raw ids across both batches, which is why its numbers do not describe either batch.

## Rejected in this search

The full list, with the licence as written and the reason, is in section 3 of [LICENSES.md](../../LICENSES.md) ("Conjuntos avaliados e não usados"): the cashew kernel conveyor paper (data availability could not be read), a Roboflow cashew set (page refused access), two Hugging Face sets without licence or origin, a GitHub fruit-defect set without licence, a Mendeley cashew-apple set that is only a PDF, a cocoa-bean conveyor set (kept as a candidate), the YouTube videos used by the apple paper, and two Commons videos (one a likely re-upload, one a filmed meeting).

Stock-video sites were not searched: their own licences are not among the open licences this project accepts, and their terms on machine-learning use were not reviewed.
