"""Run Stage 3 on an existing preprocessed image directory."""

import argparse
import json
from pathlib import Path

from src.drawing_analysis.pipeline import AnalysisConfig, analyze_preprocessed_directory, save_analysis
from src.utils.traceability import allocate_output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract inspectable candidates from a preprocessed Ship GA drawing.")
    parser.add_argument("preprocessed_dir", type=Path, help="Directory containing final.png")
    parser.add_argument("--config", type=Path, default=Path("config/default.json"))
    parser.add_argument("--output-dir", type=Path, help="Directory for separate analysis results")
    parser.add_argument("--run-id", help="Stable run identifier; reruns otherwise use a generated directory when outputs exist")
    args = parser.parse_args()
    values = json.loads(args.config.read_text(encoding="utf-8"))
    config = AnalysisConfig(**values.get("analysis", {}))
    result = analyze_preprocessed_directory(args.preprocessed_dir, config)
    base_dir = args.output_dir or args.preprocessed_dir.parent.parent / "analysis" / args.preprocessed_dir.name
    output_dir, run_id = allocate_output_dir(base_dir, ("report.json", "overlay.png"), args.run_id)
    paths = save_analysis(result, output_dir, args.preprocessed_dir / "final.png", run_id=run_id)
    print(f"Saved {len(paths)} analysis outputs to {output_dir} (run {run_id})")


if __name__ == "__main__":
    main()
