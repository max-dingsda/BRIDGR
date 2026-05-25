from pathlib import Path

from run_artifacts import load_latest_run, write_latest_run


def test_load_latest_run_reads_saved_payload(tmp_path: Path) -> None:
    payload = {"run_mode": "delta", "documents": [{"source_path": "Input/test.bpmn", "status": "processed"}]}

    write_latest_run(payload, tmp_path)
    loaded_payload = load_latest_run(tmp_path)

    assert loaded_payload == payload


def test_load_latest_run_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_latest_run(tmp_path) is None
