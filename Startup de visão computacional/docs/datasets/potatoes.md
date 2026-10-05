# Dataset card: Potatoes Dataset

Source, licence, hashes and attribution: [data/external/potatoes/SOURCE.md](../../data/external/potatoes/SOURCE.md). Label mapping: [data/label_map.json](../../data/label_map.json). Produced by `python scripts/convert_external.py`.

- Setting: **real industrial conveyor sorting line (Basler camera perpendicular to the belt)**
- Fruit: potato
- Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (allowed with attribution)
- Processed images: 128x128 px RGB PNG, the classifier's input size, in `data/processed/<set>/images/<split>/<label>/`, with `manifest.csv`

## Before mapping

```json
{
 "files": {
  "Damaged": 1108,
  "Good": 1236,
  "Plant": 929,
  "Stone": 872
 },
 "unique_objects": {
  "Damaged": 110,
  "Good": 560,
  "Plant": 44,
  "Stone": 43
 },
 "near_duplicate_pairs_merged": 51
}
```

## After mapping (counts of files on disk)

### `potatoes`

| Split | good | poor_or_rotten | Total |
|---|---|---|---|
| train | 387 | 80 | 467 |
| val | 91 | 13 | 104 |
| test | 82 | 17 | 99 |
| all | 560 | 110 | 670 |

Split by group (sha256 of the group id, 70/15/15). Duplicate check across splits:

```json
{
 "exact_duplicate_images_in_two_splits": 0,
 "phash_candidate_pairs_across_splits": 0,
 "confirmed_near_duplicates_across_splits": 0,
 "rule": "candidates: 64-bit DCT perceptual hash, Hamming distance <= 6; confirmed: Pearson correlation of the 128x128 RGB images >= 0.99",
 "highest_candidate_correlation": 0.0,
 "confirmed_examples": [],
 "groups_in_two_splits": 0
}
```

### `potatoes_foreign_objects`

| Split | plant | stone | Total |
|---|---|---|---|
| train | 32 | 31 | 63 |
| val | 8 | 3 | 11 |
| test | 4 | 9 | 13 |
| all | 44 | 43 | 87 |

Split by group (sha256 of the group id, 70/15/15). Duplicate check across splits:

```json
{
 "exact_duplicate_images_in_two_splits": 0,
 "phash_candidate_pairs_across_splits": 0,
 "confirmed_near_duplicates_across_splits": 0,
 "rule": "candidates: 64-bit DCT perceptual hash, Hamming distance <= 6; confirmed: Pearson correlation of the 128x128 RGB images >= 0.99",
 "highest_candidate_correlation": 0.0,
 "confirmed_examples": [],
 "groups_in_two_splits": 0
}
```

## Known limitations

- Real industrial sorting line, but only 50x50 px crops of single objects are published: no full frames, no video, so segmentation, tracking and counting cannot be trained or tested with it.
- Heavy duplication: 4,145 files hold 1,294 pixel-unique images and 757 objects once rotations and flips are counted; 224 of the 288 objects in the official test folders also appear in train or val. The official splits are not used here.
- `Damaged` mixes cut, rotten and diseased potatoes; it stays one merged label (`poor_or_rotten`).
- Potato, not cashew; the belt is grey-blue and close to potato colour.

## How it may be used

- test how a classifier or a segmentation rule behaves on real belt imagery (background, lighting, motion blur, touching neighbours)
- pre-train or evaluate a good-versus-damaged head and a foreign-object detector for belts
- commercial use, with the attribution in SOURCE.md (CC BY 4.0)

## How it may not be used

- be presented as cashew data or as cashew-on-belt data
- be used to report accuracy of the cashew product
- be evaluated on its official splits as if they were independent
