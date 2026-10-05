# Datasets: index

| Document | What it is |
|---|---|
| [a2_search_report.md](a2_search_report.md) | The time-boxed search for fruit-on-belt datasets: what was checked, why each candidate was rejected, and the three known datasets recorded but not downloaded |
| [potatoes.md](potatoes.md) | Card: Potatoes Dataset (University of Pardubice), real industrial sorting line, CC BY 4.0 |
| [lemons.md](lemons.md) | Card: Lemons quality control dataset (SoftwareMill), lab rig, MIT |
| [fruitnet.md](fruitnet.md) | Card: FruitNet (Meshram and Patil), phone photos, CC BY 4.0 |
| [a5_background_sensitivity.md](a5_background_sensitivity.md) | A5: the current model on potato and lemon crops, as published and with a grey background; measures background sensitivity, not cashew accuracy |
| `a5_measurement.json`, `a5_mask_examples_*.png` | The raw A5 numbers and the mask examples |
| [potatoes/](potatoes/) | Earlier evaluation of the segmentation rule and training recipe on the potato line (CAMERA.md section 7) |
| [cashew_label_audit/](cashew_label_audit/) | Audit of the cashew training labels (two class numberings; CAMERA.md section 3) |
| `test_datasets_run.txt` | Output of `python manage.py test core.test_datasets -v 2` |

Where the data lives (not committed, see `.gitignore`): `data/external/<id>/raw/` (archives as downloaded), `data/external/<id>/extracted/`, `data/external/<id>/SOURCE.md` (committed), `data/processed/<set>/` (128 px crops and `manifest.csv`), `data/label_map.json` (committed). Rebuild everything with:

```powershell
python scripts/fetch_datasets.py
python scripts/convert_external.py
python scripts/measure_external.py
```
