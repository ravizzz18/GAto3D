"""Inspectable, heuristic feature extraction for preprocessed drawings.

This module deliberately produces candidates rather than semantic predictions.
OCR and ship-component classification are outside the scope of this stage.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class AnalysisConfig:
    canny_low_threshold: int = 50
    canny_high_threshold: int = 150
    hough_threshold: int = 50
    hough_min_line_length_ratio: float = 0.02
    hough_max_line_gap: int = 12
    horizontal_angle_tolerance_degrees: float = 8.0
    vertical_angle_tolerance_degrees: float = 8.0
    contour_dilation_kernel_size: int = 3
    contour_min_area_ratio: float = 0.00001
    contour_max_area_ratio: float = 0.90
    text_min_area: int = 8
    text_max_area: int = 20000
    text_min_width: int = 2
    text_max_width: int = 500
    text_min_height: int = 2
    text_max_height: int = 200
    text_merge_kernel_size: int = 9
    drawing_min_area_ratio: float = 0.005
    drawing_min_line_density: float = 0.01
    max_detection_dimension: int = 4000


@dataclass
class AnalysisResult:
    config: AnalysisConfig
    lines: dict[str, list[dict[str, Any]]]
    contours: list[dict[str, Any]]
    text_regions: list[dict[str, Any]]
    drawing_regions: list[dict[str, Any]]
    visualisations: dict[str, np.ndarray]
    diagnostics: dict[str, Any]


def _validate_config(config: AnalysisConfig) -> None:
    if config.max_detection_dimension < 100:
        raise ValueError("max_detection_dimension must be at least 100")
    if config.text_merge_kernel_size < 1 or config.text_merge_kernel_size % 2 == 0:
        raise ValueError("text_merge_kernel_size must be a positive odd number")
    if config.contour_dilation_kernel_size < 1 or config.contour_dilation_kernel_size % 2 == 0:
        raise ValueError("contour_dilation_kernel_size must be a positive odd number")
    if not 0 <= config.horizontal_angle_tolerance_degrees < 45:
        raise ValueError("horizontal_angle_tolerance_degrees must be in [0, 45)")
    if not 0 <= config.vertical_angle_tolerance_degrees < 45:
        raise ValueError("vertical_angle_tolerance_degrees must be in [0, 45)")
    if not 0 < config.contour_min_area_ratio <= config.contour_max_area_ratio <= 1:
        raise ValueError("contour area ratios must satisfy 0 < min <= max <= 1")


def _binary_image(image: np.ndarray) -> np.ndarray:
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    if grayscale.dtype != np.uint8:
        grayscale = cv2.normalize(grayscale, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return grayscale, (grayscale < 128).astype(np.uint8) * 255


def _detection_image(grayscale: np.ndarray, binary: np.ndarray, max_dimension: int) -> tuple[np.ndarray, np.ndarray, float]:
    scale = min(1.0, max_dimension / max(grayscale.shape))
    if scale == 1.0:
        return grayscale, binary, 1.0
    size = (max(1, int(grayscale.shape[1] * scale)), max(1, int(grayscale.shape[0] * scale)))
    resized_binary = cv2.resize(binary, size, interpolation=cv2.INTER_AREA)
    return cv2.resize(grayscale, size, interpolation=cv2.INTER_AREA), (resized_binary >= 128).astype(np.uint8) * 255, scale


def _box(x: int, y: int, width: int, height: int, scale: float) -> dict[str, int]:
    return {
        "x": int(round(x / scale)),
        "y": int(round(y / scale)),
        "width": int(round(width / scale)),
        "height": int(round(height / scale)),
    }


def _detect_lines(edges: np.ndarray, config: AnalysisConfig, scale: float) -> dict[str, list[dict[str, Any]]]:
    height, width = edges.shape
    minimum_length = max(10, int(min(height, width) * config.hough_min_line_length_ratio))
    raw = cv2.HoughLinesP(edges, 1, np.pi / 180, config.hough_threshold, minLineLength=minimum_length, maxLineGap=config.hough_max_line_gap)
    lines: dict[str, list[dict[str, Any]]] = {"horizontal": [], "vertical": [], "diagonal": []}
    if raw is None:
        return lines
    for values in raw[:, 0]:
        x1, y1, x2, y2 = (int(value) for value in values)
        angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180)
        length = float(np.hypot(x2 - x1, y2 - y1) / scale)
        if min(angle, 180 - angle) <= config.horizontal_angle_tolerance_degrees:
            category = "horizontal"
        elif abs(angle - 90) <= config.vertical_angle_tolerance_degrees:
            category = "vertical"
        else:
            category = "diagonal"
        lines[category].append({
            "x1": int(round(x1 / scale)), "y1": int(round(y1 / scale)),
            "x2": int(round(x2 / scale)), "y2": int(round(y2 / scale)),
            "angle_degrees": round(angle, 3), "length": round(length, 3),
        })
    return lines


def _detect_contours(binary: np.ndarray, config: AnalysisConfig, scale: float) -> list[dict[str, Any]]:
    image_area = binary.shape[0] * binary.shape[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (config.contour_dilation_kernel_size,) * 2)
    contour_source = cv2.dilate(binary, kernel, iterations=1)
    contours, _ = cv2.findContours(contour_source, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    result = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not image_area * config.contour_min_area_ratio <= area <= image_area * config.contour_max_area_ratio:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        result.append({"bbox": _box(x, y, width, height, scale), "area": round(float(area / scale**2), 3), "perimeter": round(float(cv2.arcLength(contour, True) / scale), 3)})
    return sorted(result, key=lambda item: item["area"], reverse=True)


def _detect_text_regions(binary: np.ndarray, config: AnalysisConfig, scale: float) -> list[dict[str, Any]]:
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (config.text_merge_kernel_size, config.text_merge_kernel_size))
    merged = cv2.dilate(binary, kernel, iterations=1)
    count, _, stats, _ = cv2.connectedComponentsWithStats(merged, connectivity=8)
    regions = []
    for index in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[index])
        original_area = int((binary[y:y + height, x:x + width] > 0).sum())
        if not (config.text_min_width <= width <= config.text_max_width and config.text_min_height <= height <= config.text_max_height):
            continue
        if not (config.text_min_area <= original_area <= config.text_max_area):
            continue
        regions.append({"bbox": _box(x, y, width, height, scale), "foreground_area": int(round(original_area / scale**2)), "candidate_type": "text_region"})
    return sorted(regions, key=lambda item: (item["bbox"]["y"], item["bbox"]["x"]))


def _detect_drawing_regions(binary: np.ndarray, lines: dict[str, list[dict[str, Any]]], config: AnalysisConfig, scale: float) -> list[dict[str, Any]]:
    image_area = binary.shape[0] * binary.shape[1]
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * config.drawing_min_area_ratio:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        roi = binary[y:y + height, x:x + width]
        density = float((roi > 0).mean())
        if density < config.drawing_min_line_density:
            continue
        regions.append({"bbox": _box(x, y, width, height, scale), "area": round(float(area / scale**2), 3), "line_density": round(density, 6), "candidate_type": "drawing_region"})
    return sorted(regions, key=lambda item: item["area"], reverse=True)


def _visualise(shape: tuple[int, int], lines: dict[str, list[dict[str, Any]]], contours: list[dict[str, Any]], text_regions: list[dict[str, Any]], drawing_regions: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    base = np.full((*shape, 3), 255, dtype=np.uint8)
    line_image, contour_image, text_image, drawing_image = (base.copy() for _ in range(4))
    colors = {"horizontal": (255, 0, 0), "vertical": (0, 180, 0), "diagonal": (0, 0, 220)}
    for category, values in lines.items():
        for line in values:
            cv2.line(line_image, (line["x1"], line["y1"]), (line["x2"], line["y2"]), colors[category], 2)
    for item in contours:
        box = item["bbox"]
        cv2.rectangle(contour_image, (box["x"], box["y"]), (box["x"] + box["width"], box["y"] + box["height"]), (0, 120, 255), 2)
    for item in text_regions:
        box = item["bbox"]
        cv2.rectangle(text_image, (box["x"], box["y"]), (box["x"] + box["width"], box["y"] + box["height"]), (180, 0, 180), 2)
    for item in drawing_regions:
        box = item["bbox"]
        cv2.rectangle(drawing_image, (box["x"], box["y"]), (box["x"] + box["width"], box["y"] + box["height"]), (0, 140, 0), 3)
    overlay = cv2.addWeighted(line_image, 0.75, contour_image, 0.35, 0)
    overlay = cv2.addWeighted(overlay, 0.8, text_image, 0.45, 0)
    overlay = cv2.addWeighted(overlay, 0.8, drawing_image, 0.45, 0)
    return {"lines": line_image, "contours": contour_image, "text_regions": text_image, "drawing_regions": drawing_image, "overlay": overlay}


def analyze_image(image: np.ndarray, config: AnalysisConfig | None = None) -> AnalysisResult:
    config = config or AnalysisConfig()
    _validate_config(config)
    if image is None or image.size == 0:
        raise ValueError("image must be a non-empty array")
    started = perf_counter()
    grayscale, binary = _binary_image(image)
    detection_gray, detection_binary, scale = _detection_image(grayscale, binary, config.max_detection_dimension)
    edges = cv2.Canny(detection_gray, config.canny_low_threshold, config.canny_high_threshold)
    lines = _detect_lines(edges, config, scale)
    contours = _detect_contours(detection_binary, config, scale)
    text_regions = _detect_text_regions(detection_binary, config, scale)
    drawing_regions = _detect_drawing_regions(detection_binary, lines, config, scale)
    return AnalysisResult(
        config=config,
        lines=lines, contours=contours, text_regions=text_regions, drawing_regions=drawing_regions,
        visualisations=_visualise(grayscale.shape, lines, contours, text_regions, drawing_regions),
        diagnostics={"image_width": int(grayscale.shape[1]), "image_height": int(grayscale.shape[0]), "detection_scale": scale, "line_counts": {key: len(value) for key, value in lines.items()}, "contour_count": len(contours), "text_region_count": len(text_regions), "drawing_region_count": len(drawing_regions), "processing_time_seconds": perf_counter() - started, "quality": "CANDIDATES_ONLY", "limitations": ["heuristic detections require visual review", "no OCR or ship-component classification", "accuracy is not measured without ground-truth annotations"]},
    )


def analyze_preprocessed_directory(directory: str | Path, config: AnalysisConfig | None = None) -> AnalysisResult:
    path = Path(directory) / "final.png"
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"Preprocessed final image not found: {path}")
    return analyze_image(image, config)


def save_analysis(result: AnalysisResult, output_dir: str | Path, source_image: str | Path | None = None) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, image in result.visualisations.items():
        path = output / f"{name}.png"
        if not cv2.imwrite(str(path), image):
            raise OSError(f"Unable to write analysis visualisation: {path}")
        paths[name] = path
    report = {"stage": "drawing_analysis", "source_image": str(source_image) if source_image else None, "config": asdict(result.config), "lines": result.lines, "contours": result.contours, "text_regions": result.text_regions, "drawing_regions": result.drawing_regions, "diagnostics": result.diagnostics, "outputs": {key: str(value) for key, value in paths.items()}}
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    paths["report"] = report_path
    return paths
