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
No detection or OCR accuracy is claimed because no ground-truth annotations exist.
