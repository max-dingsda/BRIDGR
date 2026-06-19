from pathlib import Path

import pytest

from processing.cmdb import (
    CMDB_ENTITY_TYPE_APPLICATION,
    CMDB_ENTITY_TYPE_SERVER,
    CmdbLoadError,
    load_cmdb_rows,
    load_normalized_cmdb,
    normalize_cmdb_entities,
    normalize_cmdb_relations,
    validate_cmdb_entity_file,
    validate_cmdb_relation_file,
)


def test_load_cmdb_rows_reads_valid_csv(tmp_path: Path) -> None:
    cmdb_path = tmp_path / "cmdb.csv"
    cmdb_path.write_text("app_id,application_name\n1,SAP Sales\n", encoding="utf-8")

    rows = load_cmdb_rows(cmdb_path, "app_id", "application_name")

    assert rows == [{"app_id": "1", "application_name": "SAP Sales"}]


def test_load_cmdb_rows_reads_semicolon_delimited_csv(tmp_path: Path) -> None:
    cmdb_path = tmp_path / "cmdb.csv"
    cmdb_path.write_text("id;name;entity_type\n1;SAP Sales;application\n", encoding="utf-8")

    rows = load_cmdb_rows(cmdb_path, "id", "name")

    assert rows == [{"id": "1", "name": "SAP Sales", "entity_type": "application"}]


def test_load_cmdb_rows_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(CmdbLoadError):
        load_cmdb_rows(tmp_path / "missing.csv", "app_id", "application_name")


def test_load_cmdb_rows_raises_for_missing_required_columns(tmp_path: Path) -> None:
    cmdb_path = tmp_path / "cmdb.csv"
    cmdb_path.write_text("id,name\n1,SAP Sales\n", encoding="utf-8")

    with pytest.raises(CmdbLoadError):
        load_cmdb_rows(cmdb_path, "app_id", "application_name")


def test_normalize_cmdb_entities_defaults_missing_entity_type_to_application() -> None:
    entities = normalize_cmdb_entities(
        rows=[{"app_id": "1", "application_name": "SAP Sales"}],
        id_column="app_id",
        name_column="application_name",
    )

    assert len(entities) == 1
    assert entities[0].entity_type == CMDB_ENTITY_TYPE_APPLICATION
    assert entities[0].server_type is None


def test_load_normalized_cmdb_reads_extended_entity_metadata(tmp_path: Path) -> None:
    cmdb_path = tmp_path / "cmdb.csv"
    cmdb_path.write_text(
        "app_id,application_name,entity_type,server_type,owner_name\n"
        "srv-1,VM App 01,server,virtual,Team Platform\n",
        encoding="utf-8",
    )

    normalized = load_normalized_cmdb(
        cmdb_path,
        id_column="app_id",
        name_column="application_name",
        entity_type_column="entity_type",
        server_type_column="server_type",
        owner_name_column="owner_name",
    )

    assert len(normalized.entities) == 1
    assert normalized.entities[0].entity_type == CMDB_ENTITY_TYPE_SERVER
    assert normalized.entities[0].server_type == "virtual"
    assert normalized.entities[0].owner_name == "Team Platform"


def test_normalize_cmdb_entities_rejects_duplicate_ids() -> None:
    with pytest.raises(CmdbLoadError, match="doppelte ID"):
        normalize_cmdb_entities(
            rows=[
                {"app_id": "1", "application_name": "SAP Sales"},
                {"app_id": "1", "application_name": "Seller Service"},
            ],
            id_column="app_id",
            name_column="application_name",
        )


def test_normalize_cmdb_relations_reads_valid_rows() -> None:
    relations = normalize_cmdb_relations(
        rows=[{"source_id": "app-1", "relation_type": "USES_INTERFACE", "target_id": "if-1"}]
    )

    assert len(relations) == 1
    assert relations[0].source_id == "app-1"
    assert relations[0].relation_type == "USES_INTERFACE"
    assert relations[0].target_id == "if-1"


def test_normalize_cmdb_entities_raises_for_empty_entity_id() -> None:
    with pytest.raises(CmdbLoadError, match="ohne ID"):
        normalize_cmdb_entities(
            rows=[{"app_id": "", "application_name": "SAP Sales"}],
            id_column="app_id",
            name_column="application_name",
        )


def test_normalize_cmdb_entities_raises_for_empty_entity_name() -> None:
    with pytest.raises(CmdbLoadError, match="ohne Namen"):
        normalize_cmdb_entities(
            rows=[{"app_id": "1", "application_name": ""}],
            id_column="app_id",
            name_column="application_name",
        )


def test_normalize_entity_type_raises_for_unknown_type() -> None:
    with pytest.raises(CmdbLoadError, match="Unbekannter CMDB-Objekttyp"):
        normalize_cmdb_entities(
            rows=[{"app_id": "1", "application_name": "SAP Sales", "entity_type": "database"}],
            id_column="app_id",
            name_column="application_name",
            entity_type_column="entity_type",
        )


def test_normalize_server_type_raises_for_unknown_server_type() -> None:
    with pytest.raises(CmdbLoadError, match="Unbekannter Server-Typ"):
        normalize_cmdb_entities(
            rows=[{"app_id": "srv-1", "application_name": "AppServer", "entity_type": "server", "server_type": "container"}],
            id_column="app_id",
            name_column="application_name",
            entity_type_column="entity_type",
            server_type_column="server_type",
        )


def test_load_cmdb_relation_rows_reads_valid_csv(tmp_path: Path) -> None:
    from processing.cmdb import load_cmdb_relation_rows

    relations_path = tmp_path / "cmdb_relations.csv"
    relations_path.write_text("source_id,relation_type,target_id\napp-1,USES_INTERFACE,if-1\n", encoding="utf-8")

    rows = load_cmdb_relation_rows(relations_path)

    assert rows == [{"source_id": "app-1", "relation_type": "USES_INTERFACE", "target_id": "if-1"}]


def test_load_cmdb_relation_rows_reads_semicolon_delimited_csv(tmp_path: Path) -> None:
    from processing.cmdb import load_cmdb_relation_rows

    relations_path = tmp_path / "cmdb_relations.csv"
    relations_path.write_text("source_id;relation_type;target_id\napp-1;USES_INTERFACE;if-1\n", encoding="utf-8")

    rows = load_cmdb_relation_rows(relations_path)

    assert rows == [{"source_id": "app-1", "relation_type": "USES_INTERFACE", "target_id": "if-1"}]


def test_load_cmdb_relation_rows_raises_for_missing_file(tmp_path: Path) -> None:
    from processing.cmdb import load_cmdb_relation_rows

    with pytest.raises(CmdbLoadError):
        load_cmdb_relation_rows(tmp_path / "missing_relations.csv")


def test_load_cmdb_relation_rows_raises_for_missing_required_columns(tmp_path: Path) -> None:
    from processing.cmdb import load_cmdb_relation_rows

    relations_path = tmp_path / "cmdb_relations.csv"
    relations_path.write_text("source,type,target\napp-1,USES_INTERFACE,if-1\n", encoding="utf-8")

    with pytest.raises(CmdbLoadError, match="Pflichtspalten"):
        load_cmdb_relation_rows(relations_path)


def test_normalize_cmdb_relations_raises_for_incomplete_row() -> None:
    with pytest.raises(CmdbLoadError):
        normalize_cmdb_relations(
            rows=[{"source_id": "app-1", "relation_type": "", "target_id": "if-1"}]
        )


def test_build_cmdb_option_labels_formats_name_and_id() -> None:
    from processing.cmdb import build_cmdb_option_labels

    rows = [
        {"app_id": "cmdb-1", "application_name": "SAP Sales"},
        {"app_id": "cmdb-2", "application_name": "Mail System"},
    ]

    labels = build_cmdb_option_labels(rows, uuid_column="app_id", name_column="application_name")

    assert labels == ["Mail System [cmdb-2]", "SAP Sales [cmdb-1]"]


def test_find_cmdb_row_by_label_returns_matching_row() -> None:
    from processing.cmdb import find_cmdb_row_by_label

    rows = [
        {"app_id": "cmdb-1", "application_name": "SAP Sales"},
        {"app_id": "cmdb-2", "application_name": "Mail System"},
    ]

    result = find_cmdb_row_by_label(rows, "Mail System [cmdb-2]", uuid_column="app_id", name_column="application_name")

    assert result == {"app_id": "cmdb-2", "application_name": "Mail System"}


def test_find_cmdb_row_by_label_returns_none_for_unknown_label() -> None:
    from processing.cmdb import find_cmdb_row_by_label

    rows = [{"app_id": "cmdb-1", "application_name": "SAP Sales"}]

    result = find_cmdb_row_by_label(rows, "Unknown App [cmdb-99]", uuid_column="app_id", name_column="application_name")

    assert result is None


def test_validate_cmdb_entity_file_reports_row_shape_issues(tmp_path: Path) -> None:
    cmdb_path = tmp_path / "cmdb.csv"
    cmdb_path.write_text(
        "id,name,entity_type,server_type,owner_name\n"
        "app-1,SAP Sales,application,,Sales\n"
        "app-2,Salesforce,Salesdepartment\n",
        encoding="utf-8",
    )

    issues = validate_cmdb_entity_file(
        cmdb_path,
        id_column="id",
        name_column="name",
        entity_type_column="entity_type",
        server_type_column="server_type",
        owner_name_column="owner_name",
    )

    assert any(issue.line_number == 3 for issue in issues)
    assert any("Strukturfehler" in issue.message for issue in issues)


def test_validate_cmdb_relation_file_reports_incomplete_rows(tmp_path: Path) -> None:
    relations_path = tmp_path / "cmdb_relations.csv"
    relations_path.write_text(
        "source_id,relation_type,target_id\n"
        "app-1,USES_INTERFACE,\n",
        encoding="utf-8",
    )

    issues = validate_cmdb_relation_file(relations_path)

    assert len(issues) == 1
    assert issues[0].line_number == 2
    assert "Strukturfehler" in issues[0].message


def test_validate_cmdb_files_accept_semicolon_delimited_csv(tmp_path: Path) -> None:
    entity_path = tmp_path / "cmdb_entities.csv"
    relation_path = tmp_path / "cmdb_relations.csv"
    entity_path.write_text("id;name;entity_type\napp-1;SAP Sales;application\n", encoding="utf-8")
    relation_path.write_text("source_id;relation_type;target_id\napp-1;RUNS_ON;srv-1\n", encoding="utf-8")

    entity_issues = validate_cmdb_entity_file(entity_path, id_column="id", name_column="name")
    relation_issues = validate_cmdb_relation_file(relation_path)

    assert entity_issues == []
    assert relation_issues == []
