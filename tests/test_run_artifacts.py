from pathlib import Path

from run_artifacts import load_last_import_context, load_latest_run, save_last_import_selection, write_latest_run


def test_load_latest_run_reads_saved_payload(tmp_path: Path) -> None:
    payload = {"run_mode": "partial", "documents": [{"source_path": "Input/test.bpmn", "status": "processed"}]}

    write_latest_run(payload, tmp_path)
    loaded_payload = load_latest_run(tmp_path)

    assert loaded_payload == payload


def test_load_latest_run_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_latest_run(tmp_path) is None


def test_save_last_import_selection_persists_display_and_archive_metadata(tmp_path: Path) -> None:
    save_last_import_selection(
        ["Input/test.bpmn"],
        tmp_path,
        display_paths=["test.bpmn"],
        archive_path="data/input_archive/20260528_120000",
        run_mode="partial",
    )

    payload = load_last_import_context(tmp_path)

    assert payload == {
        "source_paths": ["Input/test.bpmn"],
        "display_paths": ["test.bpmn"],
        "archive_path": "data/input_archive/20260528_120000",
        "run_mode": "partial",
    }
