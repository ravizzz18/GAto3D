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

OCR uses Tesseract, selected through the `pytesseract` Python wrapper. Install
both dependencies:

```powershell
python -m pip install -r requirements.txt
```

On Windows, install the native Tesseract OCR application separately and ensure
`tesseract.exe` is on `PATH`, or set `ocr.tesseract_cmd` in
`config\default.json` to its full path. The `eng` language data must also be
installed. `input_stage` can be changed to `enhanced`, `grayscale`, or
`original`; the existing preprocessing code and parameters are not changed.

Outputs are written to:

- `outputs/images/original.png`
- `outputs/images/grayscale.png`
- `outputs/images/denoised.png`
- `outputs/images/enhanced.png`
- `outputs/images/thresholded.png`
- `outputs/images/deskewed.png`
- `outputs/images/final.png`
- `outputs/reports/<output-name>_comparison.json`

Stage 3 writes `lines.png`, `contours.png`, `text_regions.png`,
`drawing_regions.png`, `overlay.png`, and `report.json` in the selected
analysis directory. The report records source coordinates (x/y/width/height
or line endpoints), candidate properties, effective parameters, and explicit
limitations.

OCR writes:

- `outputs/ocr/extracted_text.txt`
- `outputs/ocr/ocr_results.json`
- `outputs/ocr/ocr_visualization.png`

The JSON report stores each non-empty recognized word, confidence, bounding
box, and input filename. Coordinates use the original selected image
dimensions; no resizing is applied by the OCR module.

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

## Input requirements

The input must be a readable PDF. Page numbers are one-based. High-resolution output is controlled by DPI; the default is 300 DPI. PNG is used to avoid lossy compression of thin engineering lines and small text.

## Known limitations

- Raster/vector classification is a heuristic, not full PDF content analysis.
- Deskewing is conservative and uses visible dark-pixel geometry; unusual layouts should be visually reviewed using the saved stages.
- Stage 3 uses heuristic OpenCV candidates; text regions are not OCR results and drawing regions are not ship-component classifications.
- Tesseract recognition on dense GA drawings can merge labels, miss small text, or misread engineering glyphs. Successful execution is not an accuracy result.
- OCR output must be visually reviewed and is not dimension extraction or ship-component recognition.
- No dimensions, component recognition, intermediate ship representation, 3D reconstruction, CAD, or validation stages are started.
- No metrics are reported for real drawings until an annotated dataset and evaluation protocol exist.

## Future modules

The later modules will be introduced only after real drawings and dataset requirements are examined. Interfaces should exchange structured artifacts and preserve source page/region information, assumptions, uncertainty, and validation results.
