"""Configurable Tesseract OCR for inspectable drawing text candidates."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import statistics
from typing import Any, Callable

import cv2
import numpy as np

from src.utils.traceability import write_run_manifest


class OCRError(RuntimeError):
    """Raised when OCR cannot be performed or its input is invalid."""


@dataclass(frozen=True)
class OCRConfig:
    input_stage: str = "final"
    language: str = "eng"
    page_segmentation_mode: int = 11
    engine_mode: int = 3
    minimum_confidence: float = 0.0
    tesseract_cmd: str | None = None


@dataclass
class OCRResult:
    input_image: str
    image_width: int
    image_height: int
    items: list[dict[str, Any]]
    extracted_text: str
    diagnostics: dict[str, Any]
    visualization: np.ndarray
    config: OCRConfig


def _ocr_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    confidences = [float(item["confidence"]) for item in items]
    normalized = [re.sub(r"[^A-Z0-9.]", "", item["text"].upper()) for item in items]
    duplicate_count = len(normalized) - len(set(normalized))
    return {
        "quality": "UNVERIFIED",
        "item_count": len(items),
        "empty_result": not items,
        "confidence_mean": round(statistics.mean(confidences), 3) if confidences else None,
        "confidence_median": round(statistics.median(confidences), 3) if confidences else None,
        "items_at_or_above_50": sum(confidence >= 50 for confidence in confidences),
        "items_at_or_above_70": sum(confidence >= 70 for confidence in confidences),
        "normalized_duplicate_count": duplicate_count,
        "limitations": [
            "OCR output requires visual review",
            "no accuracy is claimed without ground-truth transcription",
            "dimension parsing and component recognition are not performed",
        ],
    }


def _load_tesseract() -> tuple[Any, Any]:
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as error:
        raise OCRError("OCR dependency missing: install pytesseract and the Tesseract executable.") from error
    return pytesseract, Output


def _resolve_input(input_path: str | Path, config: OCRConfig) -> Path:
    path = Path(input_path)
    if path.is_dir():
        path = path / f"{config.input_stage}.png"
    if not path.exists():
        raise OCRError(f"OCR input image does not exist: {path}")
    if not path.is_file():
        raise OCRError(f"OCR input path is not a file: {path}")
    return path


def _as_int(value: Any, field: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError) as error:
        raise OCRError(f"Tesseract returned an invalid {field}: {value!r}") from error


def _as_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise OCRError(f"Tesseract returned an invalid confidence: {value!r}") from error


def _visualize(image: np.ndarray, items: list[dict[str, Any]]) -> np.ndarray:
    if image.ndim == 2:
        visualization = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        visualization = image.copy()
    for item in items:
        box = item["bbox"]
        top_left = (box["x"], box["y"])
        bottom_right = (box["x"] + box["width"], box["y"] + box["height"])
        cv2.rectangle(visualization, top_left, bottom_right, (0, 0, 255), 2)
        label = item["text"][:40]
        if label:
            cv2.putText(visualization, label, (box["x"], max(15, box["y"] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1, cv2.LINE_AA)
    return visualization


def run_ocr(input_path: str | Path, config: OCRConfig | None = None, data_reader: Callable[..., dict[str, Any]] | None = None) -> OCRResult:
    config = config or OCRConfig()
    if not 0 <= config.minimum_confidence <= 100:
        raise ValueError("minimum_confidence must be between 0 and 100")
    image_path = _resolve_input(input_path, config)
    image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if image is None or image.size == 0:
        raise OCRError(f"Unable to read non-empty OCR input image: {image_path}")
    pytesseract, output = _load_tesseract()
    if config.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = config.tesseract_cmd
    reader = data_reader or pytesseract.image_to_data
    options = f"--oem {config.engine_mode} --psm {config.page_segmentation_mode}"
    try:
        raw = reader(image, lang=config.language, config=options, output_type=output.DICT)
    except pytesseract.TesseractNotFoundError as error:
        raise OCRError("Tesseract executable not found. Install Tesseract OCR and configure tesseract_cmd or PATH.") from error
    except pytesseract.TesseractError as error:
        raise OCRError(f"Tesseract OCR failed: {error}") from error
    except OSError as error:
        raise OCRError(f"Unable to start Tesseract OCR: {error}") from error
    required = ("text", "conf", "left", "top", "width", "height")
    if any(key not in raw for key in required):
        raise OCRError("Tesseract response did not contain required text, confidence, and box fields.")
    items: list[dict[str, Any]] = []
    for index, text_value in enumerate(raw["text"]):
        text = str(text_value).strip()
        confidence = _as_confidence(raw["conf"][index])
        if not text or confidence < config.minimum_confidence:
            continue
        items.append({
            "text": text,
            "confidence": round(confidence, 3),
            "bbox": {
                "x": _as_int(raw["left"][index], "left"),
                "y": _as_int(raw["top"][index], "top"),
                "width": _as_int(raw["width"][index], "width"),
                "height": _as_int(raw["height"][index], "height"),
            },
            "input_image": image_path.name,
        })
    return OCRResult(
        input_image=str(image_path),
        image_width=int(image.shape[1]),
        image_height=int(image.shape[0]),
        items=items,
        extracted_text="\n".join(item["text"] for item in items),
        diagnostics=_ocr_diagnostics(items),
        visualization=_visualize(image, items),
        config=config,
    )


def extract_text(result: OCRResult) -> str:
    """Return the plain text produced by OCR without additional parsing."""
    return result.extracted_text


def save_ocr_result(result: OCRResult, output_dir: str | Path = "outputs/ocr", run_id: str | None = None) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    text_path = output / "extracted_text.txt"
    text_path.write_text(result.extracted_text, encoding="utf-8")
    visualization_path = output / "ocr_visualization.png"
    if not cv2.imwrite(str(visualization_path), result.visualization):
        raise OCRError(f"Unable to write OCR visualization: {visualization_path}")
    report = {
        "input_image": result.input_image,
        "image_dimensions": {"width": result.image_width, "height": result.image_height},
        "config": asdict(result.config),
        "items": result.items,
        "diagnostics": result.diagnostics,
        "outputs": {"extracted_text": str(text_path), "visualization": str(visualization_path)},
    }
    json_path = output / "ocr_results.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    paths = {"extracted_text": text_path, "results": json_path, "visualization": visualization_path}
    manifest = write_run_manifest(output, "ocr", run_id or output.name, [result.input_image], paths, asdict(result.config), warnings=result.diagnostics.get("limitations", []), metrics=result.diagnostics)
    paths["run_manifest"] = manifest
    return paths
