from pathlib import Path

from core.app_config import AppConfig
from processing.run_artifacts import load_last_import_context, write_latest_run
from services.import_service import build_import_completion_message, finalize_import_artifacts


def test_finalize_import_artifacts_moves_processed_files_and_updates_metadata(tmp_path: Path, monkeypatch) -> None:
    from neo4j_test_support import ScopedClientStub
    monkeypatch.setattr("services.import_service.get_session_neo4j_client", lambda _: ScopedClientStub())
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


def test_archive_retry_keeps_already_moved_files_and_finishes_metadata(tmp_path, monkeypatch):
    import pytest
    from services import import_service
    from neo4j_test_support import ScopedClientStub
    monkeypatch.setattr(import_service, "get_session_neo4j_client", lambda _: ScopedClientStub())
    monkeypatch.setattr("core.app_config.PROJECT_ROOT", tmp_path)
    source = tmp_path / "Input"
    source.mkdir()
    paths = [source / "a.txt", source / "b.txt"]
    for path in paths:
        path.write_text(path.name, encoding="utf-8")
    output = tmp_path / "Output"
    write_latest_run({"documents": []}, output)
    original = import_service.shutil.move
    def fail_second(src, dst):
        if Path(src).name == "b.txt":
            raise OSError("injected archive failure")
        return original(src, dst)
    monkeypatch.setattr(import_service.shutil, "move", fail_second)
    config = AppConfig()
    with pytest.raises(OSError, match="Graph wurde gespeichert"):
        finalize_import_artifacts(config, output, source, "full", [str(p) for p in paths])
    assert not paths[0].exists() and paths[1].exists()
    assert (output / import_service.PENDING_ARCHIVE).exists()
    monkeypatch.setattr(import_service.shutil, "move", original)
    archive, display = import_service.recover_import_artifacts(config, output)
    assert display == ["a.txt", "b.txt"]
    assert (Path(archive) / "a.txt").read_text() == "a.txt"
    assert (Path(archive) / "b.txt").read_text() == "b.txt"
    assert not (output / import_service.PENDING_ARCHIVE).exists()


def test_archiving_does_not_change_metadata_of_a_newer_run(tmp_path, monkeypatch):
    import pytest
    from services import import_service
    from neo4j_test_support import ScopedClientStub
    monkeypatch.setattr(import_service, "get_session_neo4j_client", lambda _: ScopedClientStub())
    monkeypatch.setattr("core.app_config.PROJECT_ROOT", tmp_path)
    source = tmp_path / "process.txt"
    source.write_text("old", encoding="utf-8")
    output = tmp_path / "Output"
    write_latest_run({"run_id": "newer", "documents": []}, output)
    with pytest.raises(ValueError, match="neuerer Import"):
        finalize_import_artifacts(AppConfig(), output, tmp_path, "full", [str(source)], expected_run_id="older")
    assert source.exists()
    assert import_service.load_latest_run(output) == {"run_id": "newer", "documents": []}


def test_invalid_archive_journal_can_be_stopped_without_deleting_files(tmp_path, monkeypatch):
    import pytest
    from services import import_service
    from neo4j_test_support import ScopedClientStub
    monkeypatch.setattr(import_service, "get_session_neo4j_client", lambda _: ScopedClientStub())
    journal = tmp_path / import_service.PENDING_ARCHIVE
    journal.write_text('{"old_format": true}', encoding="utf-8")
    source = tmp_path / "retained.txt"
    source.write_text("retain", encoding="utf-8")
    with pytest.raises(ValueError, match="ungültig"):
        import_service.recover_import_artifacts(AppConfig(), tmp_path)
    import_service.stop_import_archiving(AppConfig(), tmp_path)
    assert not journal.exists() and source.read_text() == "retain"
    preserved = list((tmp_path / "archive_journals").glob("*.json"))
    assert len(preserved) == 1 and preserved[0].read_text() == '{"old_format": true}'
