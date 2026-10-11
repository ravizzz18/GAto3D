"""Run OCR on one existing preprocessing output directory or image."""

import argparse
import json
from pathlib import Path

from src.ocr.pipeline import OCRConfig, OCRError, run_ocr, save_ocr_result
from src.utils.traceability import allocate_output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract text from a preprocessed Ship GA drawing.")
    parser.add_argument("input_path", type=Path, help="Preprocessed image directory or image path")
    parser.add_argument("--config", type=Path, default=Path("config/default.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/ocr"))
    parser.add_argument("--run-id", help="Stable run identifier; reruns otherwise use a generated directory when outputs exist")
    args = parser.parse_args()
    values = json.loads(args.config.read_text(encoding="utf-8"))
    config = OCRConfig(**values.get("ocr", {}))
    try:
        result = run_ocr(args.input_path, config)
        output_dir, run_id = allocate_output_dir(args.output_dir, ("ocr_results.json", "extracted_text.txt", "ocr_visualization.png"), args.run_id)
        paths = save_ocr_result(result, output_dir, run_id=run_id)
    except (OCRError, ValueError) as error:
        parser.error(str(error))
    print(f"OCR recognized {len(result.items)} items from {result.input_image} (run {run_id})")
    for path in paths.values():
        print(path)


if __name__ == "__main__":
    main()
