"""Evaluate OCR output against manually reviewed, small ground-truth sets."""

import json
from pathlib import Path
import re
from typing import Any


def normalize_text(value: str) -> str:
    return re.sub(r"[^A-Z0-9.]+", "", value.upper())


def intersection_over_union(first: dict[str, int], second: dict[str, int]) -> float:
    left = max(first["x"], second["x"])
    top = max(first["y"], second["y"])
    right = min(first["x"] + first["width"], second["x"] + second["width"])
    bottom = min(first["y"] + first["height"], second["y"] + second["height"])
    intersection = max(0, right - left) * max(0, bottom - top)
    union = first["width"] * first["height"] + second["width"] * second["height"] - intersection
    return intersection / union if union else 0.0


def evaluate_ocr(annotation_path: str | Path, result_path: str | Path, iou_threshold: float = 0.5, scope_iou_threshold: float = 0.1) -> dict[str, Any]:
    annotations = json.loads(Path(annotation_path).read_text(encoding="utf-8"))
    result = json.loads(Path(result_path).read_text(encoding="utf-8"))
    ground_truth = annotations["annotations"]
    predictions = result["items"]
    available = set(range(len(predictions)))
    matches: list[dict[str, Any]] = []
    for truth_index, truth in enumerate(ground_truth):
        candidates = [(intersection_over_union(truth["bbox"], prediction["bbox"]), index) for index, prediction in enumerate(predictions) if index in available]
        candidates = [(score, index) for score, index in candidates if score >= iou_threshold]
        if not candidates:
            matches.append({"ground_truth_index": truth_index, "prediction_index": None, "iou": 0.0, "exact_text": False})
            continue
        score, prediction_index = max(candidates)
        available.remove(prediction_index)
        matches.append({
            "ground_truth_index": truth_index,
            "prediction_index": prediction_index,
            "iou": round(score, 4),
            "exact_text": normalize_text(truth["text"]) == normalize_text(predictions[prediction_index]["text"]),
        })
    scoped_predictions = [index for index, prediction in enumerate(predictions) if any(intersection_over_union(truth["bbox"], prediction["bbox"]) >= scope_iou_threshold for truth in ground_truth)]
    matched = [match for match in matches if match["prediction_index"] is not None]
    exact = [match for match in matched if match["exact_text"]]
    dimension_matches = [match for match in matched if ground_truth[match["ground_truth_index"]]["category"] == "dimension"]
    dimension_exact = [match for match in dimension_matches if match["exact_text"]]
    return {
        "annotation_file": str(annotation_path),
        "result_file": str(result_path),
        "matching": {"iou_threshold": iou_threshold, "scope_iou_threshold": scope_iou_threshold, "text_normalization": "uppercase; remove non-alphanumeric characters except periods; one-to-one greedy IoU matching"},
        "metrics": {
            "ground_truth_count": len(ground_truth),
            "prediction_count": len(predictions),
            "scoped_prediction_count": len(scoped_predictions),
            "matched_detection_count": len(matched),
            "missed_ground_truth_count": len(ground_truth) - len(matched),
            "scoped_detection_precision": len(matched) / len(scoped_predictions) if scoped_predictions else 0.0,
            "detection_recall": len(matched) / len(ground_truth) if ground_truth else 0.0,
            "exact_recognition_count": len(exact),
            "exact_recognition_accuracy": len(exact) / len(matched) if matched else 0.0,
            "dimension_ground_truth_count": len([truth for truth in ground_truth if truth["category"] == "dimension"]),
            "dimension_matched_count": len(dimension_matches),
            "dimension_exact_count": len(dimension_exact),
            "dimension_exact_accuracy": len(dimension_exact) / len(dimension_matches) if dimension_matches else 0.0,
        },
        "matches": matches,
        "limitations": annotations.get("limitations", []),
    }


def save_evaluation(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
