from pathlib import Path

from import_utils import list_cmdb_files, list_process_files, sanitize_uploaded_name, save_uploaded_file


def test_list_process_files_returns_bpmn_and_xml(tmp_path: Path) -> None:
    (tmp_path / "a.bpmn").write_text("a", encoding="utf-8")
    (tmp_path / "b.xml").write_text("b", encoding="utf-8")
    (tmp_path / "c.csv").write_text("c", encoding="utf-8")

    result = list_process_files(tmp_path)

    assert result == [tmp_path / "a.bpmn", tmp_path / "b.xml"]


def test_save_uploaded_file_creates_parent_directories(tmp_path: Path) -> None:
    target_path = tmp_path / "nested" / "process.xml"

    save_uploaded_file(target_path, b"<definitions />")

    assert target_path.read_bytes() == b"<definitions />"


def test_sanitize_uploaded_name_strips_path_segments() -> None:
    assert sanitize_uploaded_name("folder/sub/process.xml") == "process.xml"


def test_list_cmdb_files_returns_csv_files(tmp_path: Path) -> None:
    (tmp_path / "cmdb.csv").write_text("a", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("b", encoding="utf-8")

    result = list_cmdb_files(tmp_path)

    assert result == [tmp_path / "cmdb.csv"]
