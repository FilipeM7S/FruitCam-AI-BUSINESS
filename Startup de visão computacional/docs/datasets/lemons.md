# Dataset card: Lemons quality control dataset

Source, licence, hashes and attribution: [data/external/lemons/SOURCE.md](../../data/external/lemons/SOURCE.md). Label mapping: [data/label_map.json](../../data/label_map.json). Produced by `python scripts/convert_external.py`.

- Setting: **lab rig, one lemon per image photographed from several angles; not a conveyor belt**
- Fruit: lemon
- Licence: [MIT](https://opensource.org/licenses/MIT) (allowed; keep the copyright and permission notice)
- Processed images: 128x128 px RGB PNG, the classifier's input size, in `data/processed/<set>/images/<split>/<label>/`, with `manifest.csv`

## Before mapping

```json
{
 "images": 2690,
 "images_with_region": {
  "blemish": 2048,
  "pedicel": 1245,
  "artifact": 451,
  "illness": 1743,
  "dark_style_remains": 467,
  "no_defect_region": 124,
  "gangrene": 449,
  "image_quality": 5,
  "mould": 264,
  "condition": 2
 }
}
```

## After mapping (counts of files on disk)

### `lemons`

| Split | good | poor | rotten | poor_or_rotten | Total |
|---|---|---|---|---|---|
| train | 85 | 360 | 535 | 1146 | 2126 |
| val | 37 | 55 | 109 | 141 | 342 |
| test | 2 | 55 | 40 | 125 | 222 |
| all | 124 | 470 | 684 | 1412 | 2690 |

Split by group (sha256 of the group id, 70/15/15). Duplicate check across splits:

```json
{
 "exact_duplicate_images_in_two_splits": 0,
 "phash_candidate_pairs_across_splits": 9007,
 "confirmed_near_duplicates_across_splits": 0,
 "rule": "candidates: 64-bit DCT perceptual hash, Hamming distance <= 6; confirmed: Pearson correlation of the 128x128 RGB images >= 0.99",
 "highest_candidate_correlation": 0.9755,
 "confirmed_examples": [],
 "groups_in_two_splits": 0
}
```

## Known limitations

- Lab rig with a dark background, one lemon per image; it is not a conveyor belt.
- The v1.0.0 COCO export has no image-level flags: `healthy` is derived (no defect region annotated) and `greening` cannot be used.
- `illness` has no definition in the README; it and `dark_style_remains` are kept as `poor_or_rotten`.
- Several photos (angles, positions) per lemon; all photos with the same fruit number are in one split. Two letters in the file names are undocumented and not used.
- Grouping by fruit number gives only 35 groups (5 to 197 photos each; 117 number+letter combinations, and the letters are undocumented). Split by group, validation and test hold 3 fruit numbers each and the test split has only 2 good photos: for any evaluation use cross-validation by fruit number, not this single split.
- Lemon, not cashew.

## How it may be used

- study defect regions and background sensitivity on a uniform background
- build compositing material (the defect polygons are in the raw COCO file)
- commercial use, keeping the MIT copyright and permission notice (see SOURCE.md)

## How it may not be used

- be presented as belt data or as cashew data
- be used to report accuracy of the cashew product
