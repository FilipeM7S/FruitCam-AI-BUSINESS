# A5: background sensitivity of the current model on potato and lemon crops

**What this is.** The current cashew model (`belt_v2.pt`, unchanged) classifies every converted crop of two non-cashew datasets twice: as published, and with the background replaced by constant grey using the segmentation the camera pipeline already does. **These numbers measure how much the model's output depends on the background. They are not accuracy figures for cashew or for the product**: potatoes and lemons are different fruits, and the model was trained only on cashew field photos.

In the product this model sends every fruit to manual review (no confidence level reached 95% accuracy on validation). Here the top class is used anyway, only to measure sensitivity.

How a prediction is counted as correct: `good` → boa; `poor` → baixa_qualidade; `rotten` → podre; `poor_or_rotten` (the source does not separate minor defects from rot) → baixa_qualidade or podre.

## potatoes (n = 670)

Mask quality: median 49% of the crop kept as fruit; centre of the crop kept in 55% of crops; mask kept almost everything in 0% and almost nothing in 0%. Examples (top: as published, bottom: grey background): [a5_mask_examples_potatoes.png](a5_mask_examples_potatoes.png).

### As published

| True label (n) | predicted boa | predicted baixa_qualidade | predicted podre | counted as correct | rate (95% CI) |
|---|---|---|---|---|---|
| good (560) | 23 | 303 | 234 | boa | 4.1% (2.8–6.1%) |
| poor_or_rotten (110) | 14 | 30 | 66 | baixa_qualidade or podre | 87.3% (79.8–92.3%) |

Good versus not good: accuracy 17.8%, balanced 45.7% (recall good 4.1%, recall not good 87.3%), n = 670.

### Background replaced by grey

| True label (n) | predicted boa | predicted baixa_qualidade | predicted podre | counted as correct | rate (95% CI) |
|---|---|---|---|---|---|
| good (560) | 2 | 372 | 186 | boa | 0.4% (0.1–1.3%) |
| poor_or_rotten (110) | 3 | 56 | 51 | baixa_qualidade or podre | 97.3% (92.3–99.1%) |

Good versus not good: accuracy 16.3%, balanced 48.8% (recall good 0.4%, recall not good 97.3%), n = 670.

Masking changed the predicted class for 224 of 670 crops (33.4%).

Reading: the mask is poor on this belt. It cuts holes into the potatoes and keeps parts of the grey-blue belt (see the examples), the same colour-segmentation failure measured on this dataset in CAMERA.md section 7. The grey-background numbers therefore mix background removal with damage to the fruit image and are not a clean background effect. As published, the model calls almost every potato not good.

## lemons (n = 2690)

Mask quality: median 17% of the crop kept as fruit; centre of the crop kept in 91% of crops; mask kept almost everything in 0% and almost nothing in 0%. Examples (top: as published, bottom: grey background): [a5_mask_examples_lemons.png](a5_mask_examples_lemons.png).

### As published

| True label (n) | predicted boa | predicted baixa_qualidade | predicted podre | counted as correct | rate (95% CI) |
|---|---|---|---|---|---|
| good (124) | 56 | 58 | 10 | boa | 45.2% (36.7–53.9%) |
| poor (470) | 172 | 214 | 84 | baixa_qualidade | 45.5% (41.1–50.1%) |
| rotten (684) | 345 | 166 | 173 | podre | 25.3% (22.2–28.7%) |
| poor_or_rotten (1412) | 482 | 647 | 283 | baixa_qualidade or podre | 65.9% (63.4–68.3%) |

Good versus not good: accuracy 60.3%, balanced 53.1% (recall good 45.2%, recall not good 61.1%), n = 2690.

### Background replaced by grey

| True label (n) | predicted boa | predicted baixa_qualidade | predicted podre | counted as correct | rate (95% CI) |
|---|---|---|---|---|---|
| good (124) | 118 | 2 | 4 | boa | 95.2% (89.8–97.8%) |
| poor (470) | 435 | 11 | 24 | baixa_qualidade | 2.3% (1.3–4.1%) |
| rotten (684) | 613 | 44 | 27 | podre | 3.9% (2.7–5.7%) |
| poor_or_rotten (1412) | 1307 | 21 | 84 | baixa_qualidade or podre | 7.4% (6.2–8.9%) |

Good versus not good: accuracy 12.2%, balanced 51.7% (recall good 95.2%, recall not good 8.2%), n = 2690.

Masking changed the predicted class for 1538 of 2690 crops (57.2%).

Reading: the mask cuts each lemon out cleanly (see the examples), so this is a clean background swap. With the dataset's black background the answers are spread over the three classes; with a grey background the model calls almost every lemon boa, defective or not. For these crops, the model's output depends more on the background than on the fruit.
