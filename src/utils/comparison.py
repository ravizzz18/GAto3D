"""Generate compact metadata for comparing original and processed drawings."""

import json
from pathlib import Path
from typing import Any

from PIL import Image


def build_comparison_report(original_path: str | Path, processed_path: str | Path, page_number: int, dpi: int, processing_time_seconds: float, parameters: dict[str, Any], diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    original = Path(original_path)
    processed = Path(processed_path)
    with Image.open(original) as original_image, Image.open(processed) as processed_image:
        return {
            "original": {"path": str(original), "dimensions": list(original_image.size), "format": original_image.format},
            "processed": {"path": str(processed), "dimensions": list(processed_image.size), "format": processed_image.format},
            "page": page_number,
            "rendering_dpi": dpi,
            "processing_time_seconds": processing_time_seconds,
            "parameters": parameters,
            "diagnostics": diagnostics or {},
        }


def save_comparison_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
