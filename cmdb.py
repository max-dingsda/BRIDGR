from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


CMDB_ENTITY_TYPE_APPLICATION = "application"
CMDB_ENTITY_TYPE_INTERFACE = "interface"
CMDB_ENTITY_TYPE_PROCESS = "process"
CMDB_ENTITY_TYPE_SERVER = "server"
CMDB_SERVER_TYPE_PHYSICAL = "physical"
CMDB_SERVER_TYPE_VIRTUAL = "virtual"

SUPPORTED_ENTITY_TYPES = {
    CMDB_ENTITY_TYPE_APPLICATION,
    CMDB_ENTITY_TYPE_INTERFACE,
    CMDB_ENTITY_TYPE_PROCESS,
    CMDB_ENTITY_TYPE_SERVER,
}
SUPPORTED_SERVER_TYPES = {
    CMDB_SERVER_TYPE_PHYSICAL,
    CMDB_SERVER_TYPE_VIRTUAL,
}


class CmdbLoadError(RuntimeError):
    pass


@dataclass(slots=True)
class CmdbEntity:
    entity_id: str
    name: str
    entity_type: str
    server_type: str | None = None
    owner_name: str | None = None
    raw_row: dict[str, str] | None = None


@dataclass(slots=True)
class CmdbRelation:
    source_id: str
    relation_type: str
    target_id: str
    raw_row: dict[str, str] | None = None


@dataclass(slots=True)
class NormalizedCmdb:
    entities: list[CmdbEntity]
    relations: list[CmdbRelation]


def load_cmdb_rows(path: Path, uuid_column: str, name_column: str) -> list[dict[str, str]]:
    if not path.exists():
        raise CmdbLoadError(f"CMDB-Datei wurde nicht gefunden: {path}")

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise CmdbLoadError("CMDB-Datei enthält keine Header-Zeile.")

            missing_columns = [
                column_name
                for column_name in (uuid_column, name_column)
                if column_name not in reader.fieldnames
            ]
            if missing_columns:
                missing_text = ", ".join(missing_columns)
                raise CmdbLoadError(f"CMDB-Datei enthält Pflichtspalten nicht: {missing_text}")

            return [dict(row) for row in reader]
    except csv.Error as exc:
        raise CmdbLoadError(f"CMDB-Datei konnte nicht gelesen werden: {path}") from exc


def load_normalized_cmdb(
    path: Path,
    id_column: str,
    name_column: str,
    entity_type_column: str = "entity_type",
    server_type_column: str = "server_type",
    owner_name_column: str = "owner_name",
) -> NormalizedCmdb:
    rows = load_cmdb_rows(path, id_column, name_column)
    return NormalizedCmdb(
        entities=normalize_cmdb_entities(
            rows,
            id_column=id_column,
            name_column=name_column,
            entity_type_column=entity_type_column,
            server_type_column=server_type_column,
            owner_name_column=owner_name_column,
        ),
        relations=[],
    )


def load_cmdb_relation_rows(
    path: Path,
    source_id_column: str = "source_id",
    relation_type_column: str = "relation_type",
    target_id_column: str = "target_id",
) -> list[dict[str, str]]:
    if not path.exists():
        raise CmdbLoadError(f"CMDB-Relationsdatei wurde nicht gefunden: {path}")

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise CmdbLoadError("CMDB-Relationsdatei enthält keine Header-Zeile.")

            missing_columns = [
                column_name
                for column_name in (source_id_column, relation_type_column, target_id_column)
                if column_name not in reader.fieldnames
            ]
            if missing_columns:
                missing_text = ", ".join(missing_columns)
                raise CmdbLoadError(f"CMDB-Relationsdatei enthält Pflichtspalten nicht: {missing_text}")

            return [dict(row) for row in reader]
    except csv.Error as exc:
        raise CmdbLoadError(f"CMDB-Relationsdatei konnte nicht gelesen werden: {path}") from exc


def normalize_cmdb_entities(
    rows: list[dict[str, str]],
    id_column: str,
    name_column: str,
    entity_type_column: str = "entity_type",
    server_type_column: str = "server_type",
    owner_name_column: str = "owner_name",
) -> list[CmdbEntity]:
    entities: list[CmdbEntity] = []
    seen_ids: set[str] = set()
    for row in rows:
        entity_id = (row.get(id_column) or "").strip()
        if not entity_id:
            raise CmdbLoadError(f"CMDB-Zeile ohne ID in Spalte '{id_column}'.")
        if entity_id in seen_ids:
            raise CmdbLoadError(f"CMDB enthält doppelte ID: {entity_id}")
        seen_ids.add(entity_id)

        name = (row.get(name_column) or "").strip()
        if not name:
            raise CmdbLoadError(f"CMDB-Zeile ohne Namen fuer ID '{entity_id}'.")

        entity_type = normalize_entity_type(row.get(entity_type_column, ""))
        server_type = normalize_server_type(row.get(server_type_column, ""), entity_type, entity_id)
        owner_name = normalize_optional_value(row.get(owner_name_column, ""))
        entities.append(
            CmdbEntity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                server_type=server_type,
                owner_name=owner_name,
                raw_row=dict(row),
            )
        )
    return entities


def normalize_cmdb_relations(
    rows: list[dict[str, str]],
    source_id_column: str = "source_id",
    relation_type_column: str = "relation_type",
    target_id_column: str = "target_id",
) -> list[CmdbRelation]:
    relations: list[CmdbRelation] = []
    for row in rows:
        source_id = (row.get(source_id_column) or "").strip()
        relation_type = (row.get(relation_type_column) or "").strip()
        target_id = (row.get(target_id_column) or "").strip()
        if not source_id or not relation_type or not target_id:
            raise CmdbLoadError("CMDB-Relationszeile muss source_id, relation_type und target_id enthalten.")
        relations.append(
            CmdbRelation(
                source_id=source_id,
                relation_type=relation_type,
                target_id=target_id,
                raw_row=dict(row),
            )
        )
    return relations


def normalize_entity_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return CMDB_ENTITY_TYPE_APPLICATION
    if normalized not in SUPPORTED_ENTITY_TYPES:
        supported_types = ", ".join(sorted(SUPPORTED_ENTITY_TYPES))
        raise CmdbLoadError(f"Unbekannter CMDB-Objekttyp '{value}'. Erlaubt sind: {supported_types}")
    return normalized


def normalize_server_type(value: str | None, entity_type: str, entity_id: str) -> str | None:
    normalized = (value or "").strip().lower()
    if entity_type != CMDB_ENTITY_TYPE_SERVER:
        return normalized or None
    if not normalized:
        return None
    if normalized not in SUPPORTED_SERVER_TYPES:
        supported_types = ", ".join(sorted(SUPPORTED_SERVER_TYPES))
        raise CmdbLoadError(
            f"Unbekannter Server-Typ '{value}' fuer CMDB-Objekt '{entity_id}'. Erlaubt sind: {supported_types}"
        )
    return normalized


def normalize_optional_value(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def build_cmdb_option_labels(
    cmdb_rows: list[dict[str, str]],
    uuid_column: str,
    name_column: str,
) -> list[str]:
    labels = []
    for row in cmdb_rows:
        labels.append(f"{row.get(name_column, '')} [{row.get(uuid_column, '')}]")
    return labels


def find_cmdb_row_by_label(
    cmdb_rows: list[dict[str, str]],
    selected_label: str,
    uuid_column: str,
    name_column: str,
) -> dict[str, str] | None:
    for row in cmdb_rows:
        label = f"{row.get(name_column, '')} [{row.get(uuid_column, '')}]"
        if label == selected_label:
            return row
    return None
