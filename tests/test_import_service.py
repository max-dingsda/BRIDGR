from pathlib import Path

from core.app_config import AppConfig
from processing.run_artifacts import load_last_import_context, write_latest_run
from services.import_service import build_import_completion_message, finalize_import_artifacts


def test_finalize_import_artifacts_moves_processed_files_and_updates_metadata(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "Input"
    output_dir = tmp_path / "Output"
    data_dir = tmp_path / "data"
    input_dir.mkdir()
    output_dir.mkdir()
    data_dir.mkdir()

    source_file = input_dir / "team" / "process.txt"
    source_file.parent.mkdir()
    source_file.write_text("hello", encoding="utf-8")
    write_latest_run({"run_mode": "partial", "documents": [{"source_path": str(source_file), "status": "processed"}]}, output_dir)

    monkeypatch.setattr("core.app_config.PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    archive_path, display_paths = finalize_import_artifacts(
        AppConfig(output_path="Output"),
        output_dir,
        input_dir,
        "partial",
        [str(source_file)],
    )

    assert not source_file.exists()
    assert display_paths == ["team/process.txt"]
    archived_file = Path(archive_path) / "team" / "process.txt"
    assert archived_file.exists()
    context = load_last_import_context(output_dir)
    assert context["display_paths"] == ["team/process.txt"]
    assert context["archive_path"] == archive_path
    assert context["run_mode"] == "partial"


def test_build_import_completion_message_mentions_archive() -> None:
    message = build_import_completion_message("12s", "full", "data/input_archive/20260528_120000", ["a.bpmn", "b.txt"])

    assert "Vollimport abgeschlossen in 12s." in message
    assert "2 Processdatei(en)" in message
    assert "data/input_archive/20260528_120000" in message
