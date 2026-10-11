import json
from pathlib import Path

import cv2
import numpy as np

from src.drawing_analysis.pipeline import AnalysisConfig, analyze_image, analyze_preprocessed_directory, save_analysis


def synthetic_drawing() -> np.ndarray:
    image = np.full((300, 400), 255, dtype=np.uint8)
    cv2.rectangle(image, (30, 40), (350, 250), 0, 2)
    cv2.line(image, (50, 220), (300, 70), 0, 2)
    cv2.line(image, (80, 100), (300, 100), 0, 2)
    cv2.putText(image, "GA", (120, 180), cv2.FONT_HERSHEY_SIMPLEX, 1, 0, 2)
    return image


def test_extracts_line_orientations_and_candidates() -> None:
    result = analyze_image(synthetic_drawing(), AnalysisConfig(hough_threshold=20, hough_min_line_length_ratio=0.1))
    assert result.lines["horizontal"]
    assert result.lines["vertical"]
    assert result.lines["diagonal"]
    assert result.contours
    assert result.text_regions
    assert result.diagnostics["quality"] == "CANDIDATES_ONLY"


def test_saves_separate_outputs_and_json(tmp_path: Path) -> None:
    source = tmp_path / "final.png"
    cv2.imwrite(str(source), synthetic_drawing())
    result = analyze_preprocessed_directory(tmp_path)
    paths = save_analysis(result, tmp_path / "analysis", source)
    assert {"lines", "contours", "text_regions", "drawing_regions", "overlay", "report"} <= paths.keys()
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    assert report["source_image"].endswith("final.png")
    assert report["lines"]["horizontal"]
