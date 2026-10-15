# Drone-based Agricultural Dataset for Crop Yield Estimation (cashew parts, full resolution)

- Dataset id in this project: `cashew_drone_full`
- Page: https://huggingface.co/datasets/KaraAgroAI/Drone-based-Agricultural-Dataset-for-Crop-Yield-Estimation
- DOI: https://doi.org/10.57967/hf/0959
- Version: Hugging Face revision 54ba9307e6f9ef441839a7286eee96b674993135 (last modified 2023-08-11)
- Setting: close-range drone photos of cashew trees in Ghana and Uganda, full resolution, with boxes for tree, flower and four fruit stages; not a conveyor belt
- Fruit: cashew apple
- Licence, authors and required attribution: [LICENSES.md](../../../LICENSES.md), section 3, entry `cashew_drone_full`

## Files

- `ghana_cashew.zip` (4,344,069,522 B) at https://huggingface.co/datasets/KaraAgroAI/Drone-based-Agricultural-Dataset-for-Crop-Yield-Estimation/resolve/54ba9307e6f9ef441839a7286eee96b674993135/data/Ghana/cashew.zip
  - published: sha256 719b7eea0b2e1b244b39db0cc9089908b5d39cb9edba14b2c0698a677ddfdc0a
  - not downloaded in full; see the section about partial download below
- `uganda_cashew.zip` (11,058,442,756 B) at https://huggingface.co/datasets/KaraAgroAI/Drone-based-Agricultural-Dataset-for-Crop-Yield-Estimation/resolve/54ba9307e6f9ef441839a7286eee96b674993135/data/Uganada/Cashew.zip
  - published: sha256 44fe791c169f21e12e2120015b9cf1f7356ffea9a5a6fc592509197ec734e431
  - not downloaded in full; see the section about partial download below
- `raw/datasheet.pdf` (1,408,002 B) from https://huggingface.co/datasets/KaraAgroAI/Drone-based-Agricultural-Dataset-for-Crop-Yield-Estimation/resolve/54ba9307e6f9ef441839a7286eee96b674993135/data/Drone-based%20Agricultural%20Dataset%20for%20Crop%20Yield%20Estimation.pdf
  - published: sha256 37dfb3fd32c7c9a2ac19af17009523d794a5f3e199abb1706f7862a014f85388
  - computed: md5 abd380e45f8528ab126b0a69377dc260, sha256 37dfb3fd32c7c9a2ac19af17009523d794a5f3e199abb1706f7862a014f85388
  - matches published: True

## Partial download

- Method: HTTP range requests on the pinned archive URLs; every file checked against the size and CRC-32 recorded in the archive's own index; the archives were not downloaded in full, so their published SHA-256 was not checked.
- Tool: `python tools/fetch_cashew_drone.py` (it repeats the same selection and downloads only what is missing).
- `ghana_cashew.zip`: 6,428 of 9,431 files present (1,712 of 4,715 photos, all 4,716 label files), 1,600,186,149 B.
  - Photos chosen: every photo with a spoilt fruit, then the photos richest in the scarcest stage until {'ripe': 4500, 'unripe': 3200, 'premature': 3200} boxes with a shorter side of at least 0.022 of the photo.
- `uganda_cashew.zip`: 3,098 of 6,196 files present (0 of 3,098 photos, all 3,098 label files), 3,354,734 B.

## Where the files are

- This set is large, so the archives and the extracted files are kept outside the project folder, in the directory named by `FRUITCAM_DATA_STORE` (default: `FruitCamData` in the user's home folder), under `cashew_drone_full/`. Only this card is in the project.

Recorded by `scripts/fetch_datasets.py` on 2026-10-11.
