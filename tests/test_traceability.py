import json
from pathlib import Path

import pytest

from src.utils.traceability import allocate_output_dir, collision_safe_file, write_run_manifest


def test_existing_outputs_get_a_new_run_directory(tmp_path: Path) -> None:
    (tmp_path / "final.png").write_bytes(b"baseline")
    output, run_id = allocate_output_dir(tmp_path, ("final.png",))
    assert output.parent == tmp_path / "runs"
    assert output.name == run_id
    assert output != tmp_path


def test_manifest_records_inputs_outputs_and_status(tmp_path: Path) -> None:
    manifest_path = write_run_manifest(
        tmp_path,
        "ocr",
        "test-run",
        ["input.png"],
        {"results": tmp_path / "ocr_results.json"},
        {"minimum_confidence": 50},
        metrics={"item_count": 2},
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["stage"] == "ocr"
    assert manifest["run_id"] == "test-run"
    assert manifest["status"] == "completed"
    assert manifest["inputs"] == ["input.png"]
    assert manifest["metrics"]["item_count"] == 2


def test_explicit_run_id_collision_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "runs" / "fixed").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        allocate_output_dir(tmp_path, ("report.json",), "fixed")


def test_existing_report_gets_run_id_suffix(tmp_path: Path) -> None:
    report = tmp_path / "comparison.json"
    report.write_text("old", encoding="utf-8")
    replacement = collision_safe_file(report, "new-run")
    assert replacement == tmp_path / "comparison-new-run.json"
    assert report.read_text(encoding="utf-8") == "old"
