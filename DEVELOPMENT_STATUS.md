# Development Status

| Stage | Status |
|---|---|
| 1. PDF processing | Implemented: validation, page counting, page rendering, basic raster/vector-or-mixed metadata |
| 2. Image preprocessing | Implemented: preserved stages, denoising, contrast, thresholding, conservative deskewing, line enhancement |
| 3. Drawing analysis and feature extraction | Implemented: heuristic line, contour, text-region, drawing-region candidates, visualisations, and JSON report |
| 4. OCR | Implemented: configurable Tesseract wrapper, text/confidence/boxes, plain text, JSON, and visualisation |
| 5. Dimensions | Not started |
| 6. Component detection | Not started |
| 7. Intermediate representation | Not started |
| 8. Reconstruction | Not started |
| 9. CAD | Not started |
| 10. Validation | Not started |
| 11. STEP/IGES | Not started |

## Verification

Stages 1-3 have automated behavior tests. Stage 3 was run on the existing clean
(`outputs/images/sample1`) and noisy (`outputs/images/noisy`) preprocessed
drawings; their visualisations must still be reviewed as heuristic candidates.
OCR verification on the available drawings found that the original
`final.png`/confidence-0 configuration was noisy: clean sample 3,207 items
(median confidence 41) and noisy sample 576 items (median confidence 29).
A configurable comparison using `enhanced.png` and confidence 50 reduced these
to 1,521 (median 74) and 43 (median 62), respectively, with visibly fewer
false-positive boxes. Important clean labels such as GENERAL ARRANGEMENT and
BULK CARRIER remained readable, while dimension recovery was not reliable.
These are observations, not accuracy scores; no ground-truth annotations exist.
Stage 4 now includes a small manually reviewed clean-drawing annotation set
at `outputs/ocr/ground_truth/sample1_annotations.json` and a reproducible
IoU/text-normalization evaluator. It covers selected titles, deck labels,
ship particulars, drawing labels, and six visible dimension values. It is not
a complete page transcription, so scoped metrics must not be treated as
whole-page OCR accuracy.
The evaluation report contains 18 reviewed regions: selected title/deck/
ship-label regions, two drawing-label words, and six visible dimension values.
The improved OCR matched 18/18 regions and 6/6 selected dimensions exactly
under the documented rules; scoped detection precision was 18/23 = 0.783.
These metrics are valid only for the selected subset. Because unannotated
page text and false positives are outside the annotation scope, this is not
evidence that OCR is reliable enough for general Ship GA drawings or for
Stage 5.
