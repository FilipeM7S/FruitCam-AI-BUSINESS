# Dataset card: FruitNet: Indian Fruits Dataset with quality (Good, Bad & Mixed quality)

Source, licence, hashes and attribution: [data/external/fruitnet/SOURCE.md](../../data/external/fruitnet/SOURCE.md). Label mapping: [data/label_map.json](../../data/label_map.json). Produced by `python scripts/convert_external.py`.

- Setting: **phone camera, varied backgrounds and lighting; not a conveyor belt**
- Fruit: apple, banana, guava, lime, orange, pomegranate
- Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (allowed with attribution)
- Processed images: 128x128 px RGB PNG, the classifier's input size, in `data/processed/<set>/images/<split>/<label>/`, with `manifest.csv`

## Before mapping

```json
{
 "files": {
  "Bad/apple": 1141,
  "Bad/banana": 1087,
  "Bad/guava": 1129,
  "Bad/lime": 1085,
  "Bad/orange": 1159,
  "Bad/pomegranate": 1187,
  "Good/apple": 1149,
  "Good/banana": 1113,
  "Good/guava": 1152,
  "Good/lime": 1094,
  "Good/orange": 1216,
  "Good/pomegranate": 5940,
  "Mixed/apple": 113,
  "Mixed/banana": 285,
  "Mixed/guava": 148,
  "Mixed/lemon": 278,
  "Mixed/orange": 125,
  "Mixed/pomegranate": 125
 },
 "grouping_pairs_within_hamming": 34895,
 "source_sizes": {
  "256x256": 12508,
  "192x256": 3968,
  "256x192": 1391,
  "3000x4000": 381,
  "8000x6000": 183
 }
}
```

## After mapping (counts of files on disk)

### `fruitnet`

| Split | good | poor_or_rotten | Total |
|---|---|---|---|
| train | 8199 | 4655 | 12854 |
| val | 1644 | 1090 | 2734 |
| test | 1821 | 1043 | 2864 |
| all | 11664 | 6788 | 18452 |

Split by group (sha256 of the group id, 70/15/15). Duplicate check across splits:

```json
{
 "exact_duplicate_images_in_two_splits": 0,
 "phash_candidate_pairs_across_splits": 13,
 "confirmed_near_duplicates_across_splits": 0,
 "rule": "candidates: 64-bit DCT perceptual hash, Hamming distance <= 6; confirmed: Pearson correlation of the 128x128 RGB images >= 0.99",
 "highest_candidate_correlation": 0.9723,
 "confirmed_examples": [],
 "groups_in_two_splits": 0
}
```

## Known limitations

- Phone photos with varied backgrounds and lighting, indoor and outdoor; not a conveyor belt.
- `Bad` mixes all defect types and rot (`poor_or_rotten`); `Mixed` images are excluded.
- No capture-session or fruit identifiers: splits use groups of near-duplicate photos (perceptual hash), which removes repeated shots but cannot guarantee that two different photos of one fruit end up in the same split.
- Apple, banana, guava, lime, orange and pomegranate; guava is the only tropical fruit and none is cashew.
- Unbalanced: good pomegranate has 5,940 images, about five times every other class; many photos come in near-identical runs of three.
- The processed folders mix 256-px images with 564 full-resolution originals (381 at 3000x4000 and 183 at 8000x6000); all are resized to 128 px here.
- Most photos show 2 to 5 fruits of the same quality, and some show hands; a label describes the whole photo, not one fruit.

## How it may be used

- test background sensitivity and pre-train generic good-versus-bad features
- commercial use, with the attribution in SOURCE.md (CC BY 4.0)

## How it may not be used

- be presented as belt data or as cashew data
- be used to report accuracy of the cashew product
