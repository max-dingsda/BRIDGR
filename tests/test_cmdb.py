from pathlib import Path

import pytest

from cmdb import (
    CMDB_ENTITY_TYPE_APPLICATION,
    CMDB_ENTITY_TYPE_SERVER,
    CmdbLoadError,
    load_cmdb_rows,
    load_normalized_cmdb,
    normalize_cmdb_entities,
    normalize_cmdb_relations,
)


def test_load_cmdb_rows_reads_valid_csv(tmp_path: Path) -> None:
    cmdb_path = tmp_path / "cmdb.csv"
    cmdb_path.write_text("app_id,application_name\n1,SAP Sales\n", encoding="utf-8")

    rows = load_cmdb_rows(cmdb_path, "app_id", "application_name")

    assert rows == [{"app_id": "1", "application_name": "SAP Sales"}]


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
