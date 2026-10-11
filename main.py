"""Run the current PDF-to-clean-drawing milestone."""

import argparse
import json
import logging
from pathlib import Path

from src.pdf.processor import render_page
from src.preprocessing.pipeline import PreprocessingConfig, load_image, preprocess_image, save_stages
from src.utils.comparison import build_comparison_report, save_comparison_report
from src.utils.traceability import allocate_output_dir, collision_safe_file, write_run_manifest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


def load_config(path: Path) -> tuple[int, PreprocessingConfig]:
    values = json.loads(path.read_text(encoding="utf-8"))
    return int(values["rendering"]["dpi"]), PreprocessingConfig(**values["preprocessing"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Render and preprocess one page of a Ship GA PDF.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, default=1, help="One-based PDF page number")
    parser.add_argument("--config", type=Path, default=Path("config/default.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/images"))
    parser.add_argument("--report", type=Path, help="Comparison report path")
    parser.add_argument("--run-id", help="Stable run identifier; reruns otherwise use a generated directory when outputs exist")
    args = parser.parse_args()
    dpi, config = load_config(args.config)
    output_dir, run_id = allocate_output_dir(args.output_dir, ("original.png", "final.png"), args.run_id)
    original_path = output_dir / "original.png"
    render_page(args.pdf, args.page, original_path, dpi=dpi)
    LOGGER.info("Rendered page %d at %d DPI", args.page, dpi)
    result = preprocess_image(load_image(original_path), config)
    paths = save_stages(result, output_dir)
    report = build_comparison_report(original_path, paths["final"], args.page, dpi, result.processing_time_seconds, config.__dict__, result.diagnostics)
    report_path = collision_safe_file(args.report, run_id) if args.report else Path("outputs/reports") / f"{run_id}_comparison.json"
    save_comparison_report(report, report_path)
    write_run_manifest(
        output_dir, "preprocessing", run_id, [args.pdf, args.config],
        {**paths, "comparison_report": report_path},
        {"rendering_dpi": dpi, "preprocessing": config.__dict__},
        warnings=result.diagnostics["warnings"],
        metrics=result.diagnostics,
    )
    LOGGER.info("Preprocessing completed in %.3f seconds", result.processing_time_seconds)
    LOGGER.info("Saved %d image stages to %s", len(paths), output_dir)
    for warning in result.diagnostics["warnings"]:
        LOGGER.warning("%s", warning)


if __name__ == "__main__":
    main()
