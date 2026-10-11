"""Evaluate OCR output against manually reviewed annotations."""

import argparse
from pathlib import Path

from src.ocr.evaluation import evaluate_ocr, save_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate OCR results against manual annotations.")
    parser.add_argument("annotations", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/ocr/evaluation/report.json"))
    args = parser.parse_args()
    report = evaluate_ocr(args.annotations, args.results)
    save_evaluation(report, args.output)
    print(report["metrics"])


if __name__ == "__main__":
    main()
