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


@dataclass(slots=True)
class CmdbValidationIssue:
    line_number: int
    message: str


def _build_csv_reader(handle, *, dict_reader: bool):
    sample = handle.read(4096)
    handle.seek(0)
    dialect = _detect_csv_dialect(sample)
    if dict_reader:
        return csv.DictReader(handle, dialect=dialect)
    return csv.reader(handle, dialect=dialect)


def _detect_csv_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        return csv.excel


def load_cmdb_rows(path: Path, uuid_column: str, name_column: str) -> list[dict[str, str]]:
    if not path.exists():
        raise CmdbLoadError(f"CMDB-Datei wurde nicht gefunden: {path}")

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = _build_csv_reader(handle, dict_reader=True)
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


def validate_cmdb_entity_file(
    path: Path,
    id_column: str,
    name_column: str,
    entity_type_column: str = "entity_type",
    server_type_column: str = "server_type",
    owner_name_column: str = "owner_name",
) -> list[CmdbValidationIssue]:
    try:
        rows = load_cmdb_rows(path, id_column, name_column)
    except CmdbLoadError as exc:
        return [CmdbValidationIssue(line_number=1, message=str(exc))]

    issues = _collect_csv_shape_issues(path)
    issues.extend(
        _validate_entity_rows(
            rows,
            id_column=id_column,
            name_column=name_column,
            entity_type_column=entity_type_column,
            server_type_column=server_type_column,
            owner_name_column=owner_name_column,
        )
    )
    return issues


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


def _collect_csv_shape_issues(path: Path) -> list[CmdbValidationIssue]:
    issues: list[CmdbValidationIssue] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = _build_csv_reader(handle, dict_reader=False)
            header = next(reader, None)
            if header is None:
                return issues
            expected_length = len(header)
            for line_number, row in enumerate(reader, start=2):
                if len(row) != expected_length:
                    issues.append(
                        CmdbValidationIssue(
                            line_number=line_number,
                            message=(
                                f"nicht importiert wegen Strukturfehler "
                                f"({len(row)} statt {expected_length} Spalten)"
                            ),
                        )
                    )
    except (OSError, csv.Error, UnicodeDecodeError):
        return issues
    return issues


def _validate_entity_rows(
    rows: list[dict[str, str]],
    id_column: str,
    name_column: str,
    entity_type_column: str,
    server_type_column: str,
    owner_name_column: str,
) -> list[CmdbValidationIssue]:
    issues: list[CmdbValidationIssue] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=2):
        entity_id = (row.get(id_column) or "").strip()
        if not entity_id:
            issues.append(CmdbValidationIssue(index, f"nicht importiert wegen Strukturfehler (ID in Spalte '{id_column}' fehlt)"))
            continue
        if entity_id in seen_ids:
            issues.append(CmdbValidationIssue(index, f"nicht importiert wegen Strukturfehler (doppelte ID '{entity_id}')"))
            continue
        seen_ids.add(entity_id)

        name = (row.get(name_column) or "").strip()
        if not name:
            issues.append(CmdbValidationIssue(index, f"nicht importiert wegen Strukturfehler (Name fuer ID '{entity_id}' fehlt)"))
            continue

        try:
            entity_type = normalize_entity_type(row.get(entity_type_column, ""))
            normalize_server_type(row.get(server_type_column, ""), entity_type, entity_id)
            normalize_optional_value(row.get(owner_name_column, ""))
        except CmdbLoadError as exc:
            issues.append(CmdbValidationIssue(index, f"nicht importiert wegen Strukturfehler ({exc})"))
    return issues


def parse_relation_columns(
    row: dict[str, str],
    source_id: str,
    runs_on_column: str,
    uses_interfaces_column: str,
    separator: str,
) -> list[CmdbRelation]:
    """Parse multi-value relation columns from an application row into CmdbRelation objects."""
    relations: list[CmdbRelation] = []
    for column, relation_type in (
        (runs_on_column, "RUNS_ON"),
        (uses_interfaces_column, "USES_INTERFACE"),
    ):
        raw_value = (row.get(column) or "").strip()
        if not raw_value:
            continue
        for target_id in raw_value.split(separator):
            target_id = target_id.strip()
            if target_id:
                relations.append(CmdbRelation(source_id=source_id, relation_type=relation_type, target_id=target_id))
    return relations


def load_normalized_cmdb_from_type_files(
    type_file_paths: dict[str, Path],
    id_column: str,
    name_column: str,
    entity_type_column: str = "entity_type",
    server_type_column: str = "server_type",
    owner_name_column: str = "owner_name",
    runs_on_column: str = "runs_on",
    uses_interfaces_column: str = "uses_interfaces",
    multivalue_separator: str = "|",
) -> NormalizedCmdb:
    """Load a NormalizedCmdb from one CSV file per entity type.

    Relation columns (runs_on, uses_interfaces) are read from the application file.
    Missing files are silently skipped so partial configurations work.
    """
    all_entities: list[CmdbEntity] = []
    all_relations: list[CmdbRelation] = []

    for entity_type, path in type_file_paths.items():
        if not path.exists():
            continue
        rows = load_cmdb_rows(path, id_column, name_column)
        for row in rows:
            entity_id = (row.get(id_column) or "").strip()
            name = (row.get(name_column) or "").strip()
            if not entity_id or not name:
                raise CmdbLoadError(
                    f"CMDB-Typ-Datei '{path.name}' enthält eine Zeile ohne ID oder Name."
                )
            server_type = normalize_server_type(row.get(server_type_column, ""), entity_type, entity_id)
            owner_name = normalize_optional_value(row.get(owner_name_column, ""))
            all_entities.append(
                CmdbEntity(
                    entity_id=entity_id,
                    name=name,
                    entity_type=entity_type,
                    server_type=server_type,
                    owner_name=owner_name,
                    raw_row=dict(row),
                )
            )
            if entity_type == CMDB_ENTITY_TYPE_APPLICATION:
                all_relations.extend(
                    parse_relation_columns(
                        row,
                        source_id=entity_id,
                        runs_on_column=runs_on_column,
                        uses_interfaces_column=uses_interfaces_column,
                        separator=multivalue_separator,
                    )
                )

    return NormalizedCmdb(entities=all_entities, relations=all_relations)


def build_cmdb_option_labels(
    cmdb_rows: list[dict[str, str]],
    uuid_column: str,
    name_column: str,
) -> list[str]:
    labels = []
    for row in cmdb_rows:
        labels.append(f"{row.get(name_column, '')} [{row.get(uuid_column, '')}]")
    return sorted(labels)


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
