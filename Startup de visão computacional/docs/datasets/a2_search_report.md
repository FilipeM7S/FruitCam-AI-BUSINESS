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
| FruitRoll-360 (citrus, live factory line, sound / substandard / rotten) | https://ieee-dataport.org/documents/fruitroll-360 | Terms of Use: "This dataset is released solely for academic and research purposes. Any commercial use requires prior written permission from the authors. Users must not redistribute the dataset or any subset thereof without authorization." | Research only; IEEE DataPort login required. Commercial-use request drafted in DATA_REQUESTS.md. |
| Oranges Classification (packing-house conveyor, fresh / rotten) | https://ieee-dataport.org/documents/oranges-classification | No licence in the visible page text. The page's embedded schema.org metadata declares `"license": "https://creativecommons.org/licenses/by/4.0/"`. | Files behind an IEEE DataPort login/subscription, which this task excludes; the CC BY 4.0 appears only in machine-readable metadata, so it should be confirmed with the author. |
| Sisfrutos Papaya | https://github.com/jhony2507/Sisfrutos-Papaya | README, "License to use and download": "... on a non-commercial basis. The use of this dataset, in whole or in part, is expressly prohibited for commercial purposes." | Explicitly non-commercial; links only on request. |
