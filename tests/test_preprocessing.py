from pathlib import Path

import cv2
import numpy as np

from src.preprocessing.pipeline import PreprocessingConfig, preprocess_image, save_stages


def test_preprocessing_preserves_shape_and_writes_stages(tmp_path: Path) -> None:
    image = np.full((120, 240, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (15, 15), (220, 100), (20, 20, 20), 2)
    cv2.line(image, (20, 80), (210, 30), (30, 30, 30), 1)
    result = preprocess_image(image, PreprocessingConfig())
    assert set(result.stages) == {"original", "grayscale", "denoised", "enhanced", "thresholded", "deskewed", "final"}
    assert all(stage.shape[:2] == (120, 240) for stage in result.stages.values())
    paths = save_stages(result, tmp_path)
    assert all(path.is_file() for path in paths.values())
    assert cv2.imread(str(paths["final"]), cv2.IMREAD_GRAYSCALE) is not None


def test_adaptive_threshold_is_configurable() -> None:
    image = np.full((80, 80), 230, dtype=np.uint8)
    image[20:60, 20:60] = 30
    result = preprocess_image(image, PreprocessingConfig(threshold_method="adaptive"))
    assert set(np.unique(result.stages["thresholded"])).issubset({0, 255})


def test_background_subtraction_suppresses_broad_stain_and_keeps_thin_line() -> None:
    image = np.full((160, 240), 235, dtype=np.uint8)
    image[30:130, 30:210] = 150
    image[80:82, 20:220] = 25
    result = preprocess_image(
        image,
        PreprocessingConfig(
            threshold_method="background_subtraction",
            background_sigma=15.0,
            background_threshold=20,
            min_component_area=0,
        ),
    )
    foreground = result.stages["thresholded"] < 128
    assert foreground[81, 20:220].mean() > 0.8
    assert foreground[40:120, 40:200].mean() < 0.1
    assert "foreground_pixel_ratio" in result.diagnostics
