"""Run Stage 3 on an existing preprocessed image directory."""

import argparse
import json
from pathlib import Path

from src.drawing_analysis.pipeline import AnalysisConfig, analyze_preprocessed_directory, save_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract inspectable candidates from a preprocessed Ship GA drawing.")
    parser.add_argument("preprocessed_dir", type=Path, help="Directory containing final.png")
    parser.add_argument("--config", type=Path, default=Path("config/default.json"))
    parser.add_argument("--output-dir", type=Path, help="Directory for separate analysis results")
    args = parser.parse_args()
    values = json.loads(args.config.read_text(encoding="utf-8"))
    config = AnalysisConfig(**values.get("analysis", {}))
    result = analyze_preprocessed_directory(args.preprocessed_dir, config)
    output_dir = args.output_dir or args.preprocessed_dir.parent.parent / "analysis" / args.preprocessed_dir.name
    paths = save_analysis(result, output_dir, args.preprocessed_dir / "final.png")
    print(f"Saved {len(paths)} analysis outputs to {output_dir}")


if __name__ == "__main__":
    main()
