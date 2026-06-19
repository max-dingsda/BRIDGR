from pathlib import Path

from processing.import_utils import (
    describe_cmdb_file,
    list_cmdb_entity_files,
    list_cmdb_files,
    list_cmdb_relation_files,
    list_process_files,
    sanitize_uploaded_name,
    save_uploaded_file,
)


def test_list_process_files_returns_supported_process_documents(tmp_path: Path) -> None:
    (tmp_path / "a.bpmn").write_text("a", encoding="utf-8")
    (tmp_path / "b.xml").write_text("b", encoding="utf-8")
    (tmp_path / "c.txt").write_text("c", encoding="utf-8")
    (tmp_path / "d.csv").write_text("c", encoding="utf-8")

    result = list_process_files(tmp_path)

    assert result == [tmp_path / "a.bpmn", tmp_path / "b.xml", tmp_path / "c.txt"]


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


def test_list_cmdb_entity_files_filters_by_required_columns(tmp_path: Path) -> None:
    (tmp_path / "cmdb_entities.csv").write_text("id,name,entity_type\napp-1,SAP Sales,application\n", encoding="utf-8")
    (tmp_path / "cmdb_relations.csv").write_text("source_id,relation_type,target_id\napp-1,RUNS_ON,srv-1\n", encoding="utf-8")

    result = list_cmdb_entity_files(tmp_path, "id", "name")

    assert result == [tmp_path / "cmdb_entities.csv"]


def test_list_cmdb_relation_files_filters_by_required_columns(tmp_path: Path) -> None:
    (tmp_path / "cmdb_entities.csv").write_text("id,name,entity_type\napp-1,SAP Sales,application\n", encoding="utf-8")
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "cmdb_relations.csv").write_text(
        "source_id,relation_type,target_id\napp-1,RUNS_ON,srv-1\n",
        encoding="utf-8",
    )

    result = list_cmdb_relation_files(tmp_path, "source_id", "relation_type", "target_id")

    assert result == [nested_dir / "cmdb_relations.csv"]


def test_list_cmdb_entity_files_accepts_semicolon_delimited_csv(tmp_path: Path) -> None:
    (tmp_path / "cmdb_entities.csv").write_text("id;name;entity_type\napp-1;SAP Sales;application\n", encoding="utf-8")

    result = list_cmdb_entity_files(tmp_path, "id", "name")

    assert result == [tmp_path / "cmdb_entities.csv"]


def test_list_cmdb_relation_files_accepts_semicolon_delimited_csv(tmp_path: Path) -> None:
    (tmp_path / "cmdb_relations.csv").write_text(
        "source_id;relation_type;target_id\napp-1;RUNS_ON;srv-1\n",
        encoding="utf-8",
    )

    result = list_cmdb_relation_files(tmp_path, "source_id", "relation_type", "target_id")

    assert result == [tmp_path / "cmdb_relations.csv"]


def test_describe_cmdb_file_returns_relative_posix_path(tmp_path: Path) -> None:
    nested_dir = tmp_path / "cmdb testdata"
    nested_dir.mkdir()
    cmdb_path = nested_dir / "cmdb_entities.csv"
    cmdb_path.write_text("id,name\napp-1,SAP Sales\n", encoding="utf-8")

    assert describe_cmdb_file(cmdb_path, tmp_path) == "cmdb testdata/cmdb_entities.csv"
