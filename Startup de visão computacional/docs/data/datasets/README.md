# Datasets: index

| Document | What it is |
|---|---|
| [../../../legal/reports/dataset_search.md](../../../legal/reports/dataset_search.md) | The time-boxed search for fruit-on-belt datasets, with the licence of every candidate. It lives in `legal/` because it is about licences |
| [potatoes.md](potatoes.md) | Card: Potatoes Dataset (University of Pardubice), real industrial sorting line |
| [lemons.md](lemons.md) | Card: Lemons quality control dataset (SoftwareMill), lab rig |
| [fruitnet.md](fruitnet.md) | Card: FruitNet (Meshram and Patil), phone photos |
| [a5_background_sensitivity.md](a5_background_sensitivity.md) | A5: the current model on potato and lemon crops, as published and with a grey background; measures background sensitivity, not cashew accuracy |
| `a5_measurement.json`, `a5_mask_examples_*.png` | The raw A5 numbers and the mask examples |
| [potatoes/](potatoes) | Earlier evaluation of the segmentation rule and training recipe on the potato line (docs/guides/camera.md section 7) |
| [cashew_label_audit/](cashew_label_audit) | Audit of the cashew training labels (two class numberings; docs/guides/camera.md section 3) |
| [../../reports/tests/datasets_module_test_output.txt](../../reports/tests/datasets_module_test_output.txt) | Output of `python manage.py test core.tests.test_datasets -v 2` |

Where the data lives (not committed, see `.gitignore`): `data/external/<id>/raw/` (archives as downloaded), `data/external/<id>/extracted/`, `data/external/<id>/SOURCE.md` (committed), `data/processed/<set>/` (128 px crops and `manifest.csv`), `data/label_map.json` (committed). Rebuild everything with:

```powershell
python scripts/fetch_datasets.py
python scripts/convert_external.py
python scripts/measure_external.py
```
