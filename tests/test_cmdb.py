from pathlib import Path

import pytest

from processing.cmdb import (
    CMDB_ENTITY_TYPE_APPLICATION,
    CMDB_ENTITY_TYPE_INTERFACE,
    CMDB_ENTITY_TYPE_SERVER,
    CmdbLoadError,
    load_cmdb_rows,
    load_normalized_cmdb_from_type_files,
    normalize_cmdb_entities,
    parse_relation_columns,
    validate_cmdb_entity_file,
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


def test_parse_relation_columns_extracts_single_runs_on() -> None:
    row = {"id": "APP-001", "runs_on": "SRV-001", "uses_interfaces": ""}
    relations = parse_relation_columns(row, "APP-001", "runs_on", "uses_interfaces", "|")
    assert len(relations) == 1
    assert relations[0].source_id == "APP-001"
    assert relations[0].relation_type == "RUNS_ON"
    assert relations[0].target_id == "SRV-001"


def test_parse_relation_columns_extracts_multiple_values_with_pipe_separator() -> None:
    row = {"id": "APP-001", "runs_on": "SRV-001|SRV-002", "uses_interfaces": "IF-001|IF-002"}
    relations = parse_relation_columns(row, "APP-001", "runs_on", "uses_interfaces", "|")
    runs_on = [r for r in relations if r.relation_type == "RUNS_ON"]
    uses = [r for r in relations if r.relation_type == "USES_INTERFACE"]
    assert [r.target_id for r in runs_on] == ["SRV-001", "SRV-002"]
    assert [r.target_id for r in uses] == ["IF-001", "IF-002"]


def test_parse_relation_columns_ignores_empty_columns() -> None:
    row = {"id": "APP-001", "runs_on": "", "uses_interfaces": ""}
    relations = parse_relation_columns(row, "APP-001", "runs_on", "uses_interfaces", "|")
    assert relations == []


def test_parse_relation_columns_tolerates_missing_columns() -> None:
    row = {"id": "APP-001"}
    relations = parse_relation_columns(row, "APP-001", "runs_on", "uses_interfaces", "|")
    assert relations == []


def test_load_normalized_cmdb_from_type_files_reads_application_and_server(tmp_path: Path) -> None:
    app_file = tmp_path / "apps.csv"
    srv_file = tmp_path / "servers.csv"
    app_file.write_text("id;name;owner_name;runs_on;uses_interfaces\nAPP-1;SAP;Buchhaltung;SRV-1;IF-1\n", encoding="utf-8")
    srv_file.write_text("id;name;server_type;owner_name\nSRV-1;ns-001;virtual;IT-Betrieb\n", encoding="utf-8")

    result = load_normalized_cmdb_from_type_files(
        {"application": app_file, "server": srv_file},
        id_column="id",
        name_column="name",
    )

    assert len(result.entities) == 2
    app = next(e for e in result.entities if e.entity_type == CMDB_ENTITY_TYPE_APPLICATION)
    srv = next(e for e in result.entities if e.entity_type == CMDB_ENTITY_TYPE_SERVER)
    assert app.entity_id == "APP-1"
    assert srv.entity_id == "SRV-1"
    assert srv.server_type == "virtual"
    assert len(result.relations) == 2
    runs_on = next(r for r in result.relations if r.relation_type == "RUNS_ON")
    uses = next(r for r in result.relations if r.relation_type == "USES_INTERFACE")
    assert runs_on.target_id == "SRV-1"
    assert uses.target_id == "IF-1"


def test_load_normalized_cmdb_from_type_files_skips_missing_files(tmp_path: Path) -> None:
    app_file = tmp_path / "apps.csv"
    app_file.write_text("id;name;owner_name\nAPP-1;SAP;Buchhaltung\n", encoding="utf-8")

    result = load_normalized_cmdb_from_type_files(
        {"application": app_file, "server": tmp_path / "missing.csv"},
        id_column="id",
        name_column="name",
    )

    assert len(result.entities) == 1
    assert result.entities[0].entity_type == CMDB_ENTITY_TYPE_APPLICATION


def test_load_normalized_cmdb_from_type_files_supports_custom_separator(tmp_path: Path) -> None:
    app_file = tmp_path / "apps.csv"
    app_file.write_text("id;name;runs_on\nAPP-1;SAP;SRV-1,SRV-2\n", encoding="utf-8")

    result = load_normalized_cmdb_from_type_files(
        {"application": app_file},
        id_column="id",
        name_column="name",
        multivalue_separator=",",
    )

    assert len(result.relations) == 2
    assert {r.target_id for r in result.relations} == {"SRV-1", "SRV-2"}


def test_load_normalized_cmdb_from_type_files_empty_dict_returns_empty(tmp_path: Path) -> None:
    result = load_normalized_cmdb_from_type_files({}, id_column="id", name_column="name")
    assert result.entities == []
    assert result.relations == []


def test_validate_cmdb_files_accept_semicolon_delimited_csv(tmp_path: Path) -> None:
    entity_path = tmp_path / "cmdb_entities.csv"
    entity_path.write_text("id;name;entity_type\napp-1;SAP Sales;application\n", encoding="utf-8")

    entity_issues = validate_cmdb_entity_file(entity_path, id_column="id", name_column="name")

    assert entity_issues == []
