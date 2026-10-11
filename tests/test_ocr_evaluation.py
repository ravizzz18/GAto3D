import json
from pathlib import Path

from src.ocr.evaluation import evaluate_ocr


def test_evaluation_matches_once_and_normalizes_text(tmp_path: Path) -> None:
    annotations = {"annotations": [{"text": "BULK CARRIER", "category": "ship_particular", "bbox": {"x": 10, "y": 10, "width": 100, "height": 20}}]}
    results = {"items": [{"text": "bulk-carrier", "bbox": {"x": 10, "y": 10, "width": 100, "height": 20}}, {"text": "BULK", "bbox": {"x": 10, "y": 10, "width": 40, "height": 20}}]}
    annotation_path = tmp_path / "annotations.json"
    result_path = tmp_path / "results.json"
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
    result_path.write_text(json.dumps(results), encoding="utf-8")
    report = evaluate_ocr(annotation_path, result_path)
    assert report["metrics"]["matched_detection_count"] == 1
    assert report["metrics"]["exact_recognition_count"] == 1
    assert report["metrics"]["missed_ground_truth_count"] == 0
