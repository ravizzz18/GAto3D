"""Conservative, inspectable preprocessing for engineering drawings."""

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class PreprocessingConfig:
    denoise_kernel_size: int = 3
    contrast_clip_limit: float = 2.0
    contrast_tile_grid_size: int = 8
    threshold_method: str = "background_subtraction"
    adaptive_block_size: int = 51
    adaptive_c: int = 7
    background_sigma: float = 15.0
    background_threshold: int = 12
    morphology_open_kernel_size: int = 1
    morphology_open_iterations: int = 1
    min_component_area: int = 8
    max_component_area_ratio: float = 0.20
    deskew_threshold_degrees: float = 0.5
    line_enhancement_amount: float = 0.35


@dataclass
class PreprocessingResult:
    stages: dict[str, np.ndarray]
    processing_time_seconds: float
    deskew_angle_degrees: float
    diagnostics: dict[str, float | int | str | list[str]]


def _validate_config(config: PreprocessingConfig) -> None:
    if config.denoise_kernel_size < 1 or config.denoise_kernel_size % 2 == 0:
        raise ValueError("denoise_kernel_size must be a positive odd number")
    if config.threshold_method not in {"otsu", "adaptive_gaussian", "adaptive", "background_subtraction"}:
        raise ValueError("threshold_method must be 'otsu', 'adaptive_gaussian', 'adaptive', or 'background_subtraction'")
    if config.adaptive_block_size < 3 or config.adaptive_block_size % 2 == 0:
        raise ValueError("adaptive_block_size must be an odd number >= 3")
    if config.background_sigma <= 0 or config.background_threshold < 0:
        raise ValueError("background_sigma must be positive and background_threshold cannot be negative")
    if config.morphology_open_kernel_size < 1 or config.morphology_open_kernel_size % 2 == 0:
        raise ValueError("morphology_open_kernel_size must be a positive odd number")
    if config.morphology_open_iterations < 0 or config.min_component_area < 0:
        raise ValueError("morphology_open_iterations and min_component_area cannot be negative")
    if not 0 < config.max_component_area_ratio <= 1:
        raise ValueError("max_component_area_ratio must be in (0, 1]")


def _threshold(enhanced: np.ndarray, config: PreprocessingConfig) -> np.ndarray:
    if config.threshold_method == "otsu":
        _, thresholded = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif config.threshold_method in {"adaptive", "adaptive_gaussian"}:
        adaptive_method = cv2.ADAPTIVE_THRESH_MEAN_C if config.threshold_method == "adaptive" else cv2.ADAPTIVE_THRESH_GAUSSIAN_C
        thresholded = cv2.adaptiveThreshold(enhanced, 255, adaptive_method, cv2.THRESH_BINARY, config.adaptive_block_size, config.adaptive_c)
    else:
        background = cv2.GaussianBlur(enhanced, (0, 0), config.background_sigma)
        dark_detail = cv2.subtract(background, enhanced)
        foreground = (dark_detail >= config.background_threshold).astype(np.uint8) * 255
        thresholded = cv2.bitwise_not(foreground)

    foreground = cv2.bitwise_not(thresholded)
    if config.morphology_open_kernel_size > 1 and config.morphology_open_iterations:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (config.morphology_open_kernel_size,) * 2)
        foreground = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, kernel, iterations=config.morphology_open_iterations)
    if config.min_component_area > 1:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(foreground, connectivity=8)
        for label in range(1, count):
            if stats[label, cv2.CC_STAT_AREA] < config.min_component_area:
                foreground[labels == label] = 0
    return cv2.bitwise_not(foreground)


def _diagnostics(grayscale: np.ndarray, thresholded: np.ndarray, config: PreprocessingConfig) -> dict[str, float | int | str | list[str]]:
    foreground = thresholded < 128
    foreground_ratio = float(foreground.mean())
    original_dark_ratio = float((grayscale < 128).mean())
    edges = cv2.Canny(grayscale, 50, 150)
    edge_density = float((edges > 0).mean())
    count, _, stats, _ = cv2.connectedComponentsWithStats(foreground.astype(np.uint8), connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA] if count > 1 else np.array([], dtype=np.int32)
    largest_area = int(areas.max()) if areas.size else 0
    largest_ratio = largest_area / float(grayscale.size)
    edge_support = cv2.dilate((thresholded < 128).astype(np.uint8), np.ones((3, 3), np.uint8))
    edge_preservation = float(((edges > 0) & (edge_support > 0)).sum() / max(int((edges > 0).sum()), 1))
    warnings: list[str] = ["diagnostics are heuristic; visually review text, dimensions, and structural lines"]
    if foreground_ratio > 0.35:
        warnings.append("foreground ratio is high; review thresholded image for stain conversion")
    if largest_ratio > config.max_component_area_ratio:
        warnings.append("largest connected component is unusually large; inspect for merged stains")
    if edge_preservation < 0.30:
        warnings.append("edge preservation estimate is low; inspect thin lines and dimensions")
    return {
        "original_dark_pixel_ratio": original_dark_ratio,
        "foreground_pixel_ratio": foreground_ratio,
        "edge_density": edge_density,
        "connected_component_count": max(count - 1, 0),
        "large_connected_component_ratio": largest_ratio,
        "edge_preservation_estimate": edge_preservation,
        "quality": "WARNING",
        "warnings": warnings,
    }


def _deskew(image: np.ndarray, threshold_degrees: float) -> tuple[np.ndarray, float]:
    inverted = cv2.bitwise_not(image)
    coordinates = np.column_stack(np.where(inverted > 32))
    if len(coordinates) < 20:
        return image, 0.0
    angle = cv2.minAreaRect(coordinates.astype(np.float32))[-1]
    if angle < -45:
        angle += 90
    if abs(angle) < threshold_degrees:
        return image, 0.0
    height, width = image.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, float(angle)


def preprocess_image(image: np.ndarray, config: PreprocessingConfig | None = None) -> PreprocessingResult:
    config = config or PreprocessingConfig()
    _validate_config(config)
    if image is None or image.size == 0:
        raise ValueError("image must be a non-empty array")
    started = perf_counter()
    original = image.copy()
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    denoised = cv2.medianBlur(grayscale, config.denoise_kernel_size)
    clahe = cv2.createCLAHE(clipLimit=config.contrast_clip_limit, tileGridSize=(config.contrast_tile_grid_size,) * 2)
    enhanced = clahe.apply(denoised)
    line_enhanced = cv2.addWeighted(enhanced, 1.0 + config.line_enhancement_amount, cv2.GaussianBlur(enhanced, (0, 0), 1.0), -config.line_enhancement_amount, 0)
    thresholded = _threshold(line_enhanced, config)
    deskewed, angle = _deskew(thresholded, config.deskew_threshold_degrees)
    final = deskewed.copy()
    return PreprocessingResult(
        stages={"original": original, "grayscale": grayscale, "denoised": denoised, "enhanced": enhanced, "thresholded": thresholded, "deskewed": deskewed, "final": final},
        processing_time_seconds=perf_counter() - started,
        deskew_angle_degrees=angle,
        diagnostics=_diagnostics(grayscale, thresholded, config),
    )


def save_stages(result: PreprocessingResult, output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, image in result.stages.items():
        path = output / f"{name}.png"
        if not cv2.imwrite(str(path), image):
            raise OSError(f"Unable to write preprocessing stage: {path}")
        paths[name] = path
    return paths


def load_image(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unable to read image: {path}")
    return image
