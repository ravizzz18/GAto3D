# Automated Ship GA to 3D CAD

Research software for incrementally converting Ship General Arrangement drawings into structured information and, later, 3D/CAD geometry. The repository currently implements the first four milestones:

`PDF page -> high-resolution PNG -> conservative preprocessing -> drawing feature candidates -> OCR`

No dimension parsing, machine learning, 3D reconstruction, CAD generation, STEP/IGES export, or fabricated predictions are implemented.

## Current status

- PDF validation, page counting, raster/vector-or-mixed heuristic, and page rendering are implemented with PyMuPDF.
- Preprocessing is implemented with OpenCV and preserves each major stage: original, grayscale, denoised, enhanced, thresholded, deskewed, and final.
- The default threshold method is scale-aware background subtraction. Otsu, adaptive mean, and adaptive Gaussian methods remain selectable for comparison.
- Rendering and preprocessing parameters are stored in `config/default.json`, including background scale, threshold, morphology, and connected-component controls.
- A JSON comparison report records dimensions, page, DPI, parameters, processing time, foreground ratio, edge density, connected components, large-component ratio, and an edge-preservation estimate.
- Stage 3 extracts configurable horizontal, vertical, and diagonal line candidates, contour/shape candidates, text-region candidates, and drawing-region candidates from `final.png`.
- Stage 3 saves independent visualisations and a coordinate-bearing JSON report. Results are candidates for visual review, not accuracy measurements.
- Stage 4 provides configurable Tesseract OCR with word text, confidence, original-image coordinates, and an annotated visualisation.

## Setup

Create and activate a virtual environment, then install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run tests:

```powershell
python -m pytest
```

## Run the current pipeline

```powershell
python main.py path\to\ship_ga.pdf --page 1
```

Optional parameters:

```powershell
python main.py path\to\ship_ga.pdf --page 2 --config config\default.json --output-dir outputs\images
```

Use a separate output and report path when comparing drawings:

```powershell
python main.py path\to\ship_ga.pdf --output-dir outputs\images\sample1 --report outputs\reports\sample1_comparison.json
```

Run Stage 3 on an existing preprocessed directory without rerunning preprocessing:

```powershell
python analyze.py outputs\images\sample1 --output-dir outputs\analysis\sample1
python analyze.py outputs\images\noisy --output-dir outputs\analysis\noisy
```

Run OCR on an existing preprocessing directory:

```powershell
python ocr.py outputs\images\sample1 --output-dir outputs\ocr
```

Run identifiers and output traceability:

Each completed preprocessing, drawing-analysis, or OCR run writes a
`run_manifest.json` containing the stage, run identifier, input paths, output
paths, configuration, status, warnings, and metrics. If a requested output
directory already contains expected files, a new directory is allocated below
`runs\<generated-run-id>` instead of silently overwriting the prior run. Use
`--run-id` for a stable explicit identifier; an existing identifier is rejected.
The first run in an empty directory retains the requested path for compatibility
but still receives a unique run ID in its manifest. Explicit comparison report
paths are also collision-safe and receive a run-ID suffix when already present.

OCR uses Tesseract, selected through the `pytesseract` Python wrapper. Install
both dependencies:

```powershell
python -m pip install -r requirements.txt
```

On Windows, install the native Tesseract OCR application separately and ensure
`tesseract.exe` is on `PATH`, or set `ocr.tesseract_cmd` in
`config\default.json` to its full path. The `eng` language data must also be
installed. The current default uses `enhanced.png` with
`minimum_confidence=50` and page segmentation mode 11 (sparse text), based on
the clean/noisy comparison described below. `input_stage` can be changed to
`final`, `grayscale`, or `original`; the existing preprocessing code and
parameters are not changed.

Outputs are written to:

- `outputs/images/original.png`
- `outputs/images/grayscale.png`
- `outputs/images/denoised.png`
- `outputs/images/enhanced.png`
- `outputs/images/thresholded.png`
- `outputs/images/deskewed.png`
- `outputs/images/final.png`
- `outputs/reports/<output-name>_comparison.json`
- `outputs/images/<sample-or-run>/run_manifest.json` for preprocessing runs

Stage 3 writes `lines.png`, `contours.png`, `text_regions.png`,
`drawing_regions.png`, `overlay.png`, and `report.json` in the selected
analysis directory. The report records source coordinates (x/y/width/height
or line endpoints), candidate properties, effective parameters, and explicit
limitations.
It also writes `run_manifest.json`.

OCR writes:

- `outputs/ocr/extracted_text.txt`
- `outputs/ocr/ocr_results.json`
- `outputs/ocr/ocr_visualization.png`
- `outputs/ocr/run_manifest.json`

The JSON report stores each non-empty recognized word, confidence, bounding
box, and input filename. Coordinates use the original selected image
dimensions; no resizing is applied by the OCR module. It also records
confidence summaries and a normalized duplicate-count diagnostic for review.

Reports are marked `WARNING` because the diagnostics are heuristics and cannot certify OCR suitability without ground truth. Visual review of text, dimensions, and structural lines remains required.

The PDF type is currently reported as `raster` or `vector-or-mixed` using page image and text metadata. Full vector geometry analysis is intentionally not implemented yet.

## Repository layout

- `src/pdf/`: PDF inspection and rendering
- `src/preprocessing/`: configurable image processing
- `src/utils/`: comparison metadata
- `tests/`: behavior tests for implemented stages
- `data/`: raw, intermediate, processed, annotation, and future dataset splits
- `models/`, `training/`: reserved for later dataset-driven ML work
- `outputs/`: generated images, reports, and reserved later-stage outputs

Current generated-output layout is intentionally backward compatible:

```text
outputs/
  images/<sample-or-run>/
    original.png ... final.png
    run_manifest.json
    runs/<run-id>/                  # automatic collision-safe reruns
  analysis/<sample-or-run>/
    lines.png ... report.json
    run_manifest.json
    runs/<run-id>/
  ocr/
    extracted_text.txt
    ocr_results.json
    ocr_visualization.png
    ground_truth/
    evaluation/
    improved/
    runs/<run-id>/
```

Existing baseline, improved, evaluation, and ground-truth outputs are
preserved. Generated outputs are ignored by Git except for explicitly
force-added review annotations.

## Input requirements

The input must be a readable PDF. Page numbers are one-based. High-resolution output is controlled by DPI; the default is 300 DPI. PNG is used to avoid lossy compression of thin engineering lines and small text.

## Known limitations

- Raster/vector classification is a heuristic, not full PDF content analysis.
- Deskewing is conservative and uses visible dark-pixel geometry; unusual layouts should be visually reviewed using the saved stages.
- Stage 3 uses heuristic OpenCV candidates; text regions are not OCR results and drawing regions are not ship-component classifications.
- Tesseract recognition on dense GA drawings can merge labels, miss small text, or misread engineering glyphs. Successful execution is not an accuracy result.
- OCR output must be visually reviewed and is not dimension extraction or ship-component recognition.
- On the available clean sample, the baseline `final.png`/confidence 0 run
  produced 3,207 items (median confidence 41); `enhanced.png`/confidence 50
  produced 1,521 items (median confidence 74) and retained visible labels such
  as GENERAL ARRANGEMENT, BULK CARRIER, DECK, and MIDSHIP SECTION.
- On the available noisy sample, the baseline produced 576 items (median
  confidence 29); the enhanced/confidence-50 variant produced 43 items
  (median confidence 62) but did not reliably recover dimension values.
- These counts and labels are observations from this run, not accuracy
  measurements. No ground-truth transcription exists, and visual inspection
  still shows missed text, false detections, and duplicate words.
- A small manually reviewed clean-drawing evaluation set is available at
  `outputs/ocr/ground_truth/sample1_annotations.json`. Run
  `python evaluate_ocr.py outputs/ocr/ground_truth/sample1_annotations.json
  outputs/ocr/improved/sample1/ocr_results.json` to produce a scoped report.
  It uses one-to-one IoU matching (threshold 0.5), uppercase/punctuation
  normalization for recognition, and reports dimension exact matches
  separately. The set is deliberately incomplete; scoped precision is not
  whole-page precision and unannotated text is not scored.
- The current 18-region report matched all 18 selected regions and all six
  selected dimension values. This result is not sufficient evidence of
  whole-page OCR reliability: the set is small, was selected from clearly
  visible important regions, and does not annotate every text item or every
  false positive. The reported 1.0 recall and exact-match values therefore
  apply only to this reviewed subset.
- No dimensions, component recognition, intermediate ship representation, 3D reconstruction, CAD, or validation stages are started.
- No metrics are reported for real drawings until an annotated dataset and evaluation protocol exist.

## Future modules

The later modules will be introduced only after real drawings and dataset requirements are examined. Interfaces should exchange structured artifacts and preserve source page/region information, assumptions, uncertainty, and validation results.
