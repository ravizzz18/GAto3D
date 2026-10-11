import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.ocr.pipeline import OCRError, OCRConfig, run_ocr, save_ocr_result


def fake_reader(image, *, lang, config, output_type):
    assert image.shape == (80, 120)
    assert lang == "eng"
    assert "--psm 11" in config
    return {
        "text": ["", "DECK", "12.5"],
        "conf": ["-1", "91.5", "72"],
        "left": ["0", "10", "60"],
        "top": ["0", "20", "40"],
        "width": ["0", "40", "30"],
        "height": ["0", "12", "10"],
    }


def test_ocr_preserves_image_coordinates_and_saves_outputs(tmp_path: Path) -> None:
    image_path = tmp_path / "final.png"
    cv2.imwrite(str(image_path), np.full((80, 120), 255, dtype=np.uint8))
    result = run_ocr(image_path, OCRConfig(minimum_confidence=50), fake_reader)
    assert result.image_width == 120
    assert result.image_height == 80
    assert result.items[0]["text"] == "DECK"
    assert result.items[0]["bbox"] == {"x": 10, "y": 20, "width": 40, "height": 12}
    paths = save_ocr_result(result, tmp_path / "ocr")
    report = json.loads(paths["results"].read_text(encoding="utf-8"))
    assert report["items"][1]["input_image"] == "final.png"
    assert cv2.imread(str(paths["visualization"])).shape[:2] == (80, 120)


def test_ocr_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(OCRError, match="does not exist"):
        run_ocr(tmp_path / "missing.png", data_reader=fake_reader)


def test_ocr_allows_empty_results(tmp_path: Path) -> None:
    image_path = tmp_path / "final.png"
    cv2.imwrite(str(image_path), np.full((20, 20), 255, dtype=np.uint8))

    def empty_reader(image, **kwargs):
        return {"text": [""], "conf": ["-1"], "left": ["0"], "top": ["0"], "width": ["0"], "height": ["0"]}

    result = run_ocr(image_path, data_reader=empty_reader)
    assert result.items == []
    assert result.diagnostics["empty_result"] is True
