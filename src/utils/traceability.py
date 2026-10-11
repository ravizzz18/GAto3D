"""Shared output allocation and run-manifest helpers."""

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any, Iterable


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def allocate_output_dir(base_dir: str | Path, expected_files: Iterable[str], run_id: str | None = None) -> tuple[Path, str]:
    base = Path(base_dir)
    expected = tuple(expected_files)
    if run_id is not None:
        target = base / "runs" / run_id
        if target.exists():
            raise FileExistsError(f"Run output directory already exists: {target}")
        target.mkdir(parents=True)
        return target, run_id
    if not any((base / name).exists() for name in expected):
        base.mkdir(parents=True, exist_ok=True)
        return base, new_run_id()
    generated = new_run_id()
    target = base / "runs" / generated
    target.mkdir(parents=True, exist_ok=False)
    return target, generated


def write_run_manifest(
    output_dir: str | Path,
    stage: str,
    run_id: str,
    inputs: Iterable[str | Path],
    outputs: dict[str, str | Path],
    config: dict[str, Any],
    status: str = "completed",
    warnings: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    error: str | None = None,
) -> Path:
    output = Path(output_dir)
    manifest_path = output / "run_manifest.json"
    manifest = {
        "stage": stage,
        "run_id": run_id,
        "started_or_recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "inputs": [str(Path(path)) for path in inputs],
        "outputs": {**{name: str(Path(path)) for name, path in outputs.items()}, "run_manifest": str(manifest_path)},
        "config": config,
        "warnings": warnings or [],
        "metrics": metrics or {},
    }
    if error:
        manifest["error"] = error
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def collision_safe_file(path: str | Path, run_id: str) -> Path:
    """Return a non-overwriting path for a report requested by a caller."""
    target = Path(path)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
    candidate = target.with_name(f"{target.stem}-{run_id}{target.suffix}")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate
