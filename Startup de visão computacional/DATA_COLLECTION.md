# Recording your own belt data: tray protocol

This is the procedure for collecting labelled images of cashew on the actual belt. It is the only way to know how well FruitCam_ai works on a real line, and the fastest way to make it better. One person can run it with a laptop, the camera and a few crates of fruit.

**The idea:** people sort fruit by hand into trays first (good, poor quality, rotten). Then each tray is run across the belt **on its own**, and every image from that run gets the tray's label automatically. Nobody has to draw boxes.

---

## 1. What you need

- The camera fixed above the belt, looking straight down, as in production. A phone on a stand is enough to start; the software reads RTSP, USB or a video file.
- Even lighting (an LED panel or bar), no direct sun, and no people in the frame.
- A belt colour that contrasts with the fruit. A dark grey or blue belt works well. Cashew apples (red, yellow, green, brown) are far from a grey belt in colour, but a beige or reddish belt would be a bad choice (see section 6).
- Crates of cashew from a normal intake, and two people who know the buyer's quality standard.
- A ruler, for calibration.

## 2. Calibrate once per camera position

Edit the camera's entry in `config/cameras.json`:

- `px_per_mm`: put a ruler on the belt, take a frame, and divide pixels by millimetres (for example 160 px over 100 mm gives 1.6).
- `belt_rows`: the first and last image rows that are belt (the top and bottom edges of the belt in the picture).
- `count_line`: where the counting line is, as a fraction of the image width (0.62 means 62% across). Put it where the fruit is fully visible.
- `source`: `rtsp://user:password@camera-ip/stream`, a USB index such as `0`, or a video file.

Check it by running `python manage.py run_camera linha-1` and watching the frame on the Linha page: every fruit should get a box and be counted once.

## 3. Sort the trays

Two people sort each crate into three trays, using the buyer's standard:

| Tray | Label | What goes in |
|---|---|---|
| Good | `boa` | Sound, ripe, saleable fruit |
| Poor quality | `baixa_qualidade` | Saleable at a lower price: immature, small, bruised, cracked, blemished |
| Rotten | `podre` | Mould, decay, soft rot, fermented |

Rules:

- When the two people disagree about a fruit, put it in a separate tray and do not use it for labelled data.
- Write down what each poor-quality tray mainly contains, and put it in the batch name (`baixa_qualidade-imaturo-A`, `baixa_qualidade-machucado-B`). Today's model only knows "immature" as poor quality; the other defect types are new data.
- **Collect many more rotten and poor-quality fruit than you think you need.** On a real potato belt, the same training recipe recognised 98% of good potatoes but only 53% of damaged ones, because defects were rare in the data.

## 4. Record each tray

One tray = one **batch** with one label. Give every physical tray its own batch name and never reuse a name for different fruit.

```powershell
$env:DJANGO_SECRET_KEY = "any-long-random-string"; $env:DJANGO_HTTPS = "0"
python manage.py record_tray linha-1 --label podre --batch 2026-10-12-podre-A
python manage.py record_tray linha-1 --label boa --batch 2026-10-12-boa-A
python manage.py record_tray linha-1 --label baixa_qualidade --batch 2026-10-12-baixa_qualidade-imaturo-A
```

- Start the command, pour the tray onto the belt, and stop the command (Ctrl+C, or `--seconds N`) when the last fruit has passed.
- You can run the same tray again under the **same** batch name (more views of the same fruit). Never run it under a different name: the same fruit in two batches could end up in both training and test.
- The command refuses a batch name that was already recorded with another label.
- The Linha page shows the live frame with the stamp "COLETA" while recording, so you can see that fruit are detected and counted.
- Nothing is written to the statistics database; recording does not change the line numbers.

What gets saved (default folder `belt_data/`):

- `belt_data/<batch>/<label>/…jpg`: up to 6 crops of every fruit that crossed the counting line, as the classifier will see them;
- `belt_data/<batch>/frames/…jpg`: one full frame every 2 s. These are for training or checking the segmentation step later; we found that a plain colour rule does not separate objects from every belt (section 6);
- `belt_data/manifest.csv`: one row per crop (file, batch, label, camera, run, fruit id, size in mm, time, source, px/mm).

**How much:** the software needs at least **2 trays per class**, because test fruit must come from a different tray than training fruit. Aim for **6 or more trays per class over 3 or more days** (different lots, light and belt cleanliness), and **300+ fruit per class**. With 3 or more trays per class, one tray per class is used for validation and one for testing.

## 5. Use the data

**Fine-tune the model on your trays, with a before/after on held-out trays:**

```powershell
python tools/finetune_belt.py --data belt_data --init models/belt_v2.pt --out models/belt_ft.pt --mix-field
```

It prints the accuracy of the starting model and of the fine-tuned model on the **same test trays**, and writes `models/belt_ft_eval.json`. Use the new model only if it is better there:

```powershell
$env:FRUITCAM_MODEL_PATH = "models/belt_ft.pt"
python manage.py runserver 127.0.0.1:8000
```

**Without labels: adapt the model to the belt (AdaBN).** Record ordinary production fruit with `--label sem_rotulo` (no sorting needed), then:

```powershell
python manage.py record_tray linha-1 --label sem_rotulo --batch 2026-10-12-producao
python tools/adapt_bn.py --init models/belt_v2.pt --crops belt_data --out models/belt_v2_adabn.pt
```

This re-estimates the network's normalisation statistics on your belt's images. It needs no labels, but it cannot be checked without labelled trays, so treat it as a candidate and compare it on labelled test trays with `finetune_belt.py --init models/belt_v2_adabn.pt` (the "before" line).

## 6. Things we measured that shape this protocol

- **Field photos are not belt photos.** The current models learned from photos of cashew on trees. On a simulated belt, the same fruit images were classified much worse. Only belt data can tell the real accuracy.
- **Segmentation by colour depends on the belt.** On a real potato line (grey-blue belt, beige potatoes), our colour rule could not separate the objects from the belt: at any threshold, either most object centres were missed or most belt corners were taken as objects. Cashew colours are much further from a grey belt (median distance 41 to 61 against a threshold of 14), but this has not been checked on a real cashew belt. Check the frames folder after the first recording.
- **Defects are the hard part.** See section 3.
- **Same fruit, same split.** Splitting by tray is what makes the test honest. Do not copy files between batch folders.

## 7. Privacy and data handling

- Keep people out of the camera's view. If someone appears in a frame, delete that frame.
- Images recorded at a partner's site belong to that partner unless agreed otherwise; keep them off public places.
