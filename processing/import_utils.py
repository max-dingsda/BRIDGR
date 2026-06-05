from __future__ import annotations

import csv
from pathlib import Path


SUPPORTED_PROCESS_SUFFIXES = {".bpmn", ".xml", ".txt", ".docx", ".pdf"}
SUPPORTED_CMDB_SUFFIXES = {".csv"}


def list_process_files(root_path: Path) -> list[Path]:
    if not root_path.exists():
        return []
    return sorted(
        path
        for path in root_path.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_PROCESS_SUFFIXES
    )


def save_uploaded_file(target_path: Path, content: bytes) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)


def sanitize_uploaded_name(filename: str) -> str:
    return Path(filename).name


def list_cmdb_files(root_path: Path) -> list[Path]:
    if not root_path.exists():
        return []
    return sorted(
        path
        for path in root_path.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_CMDB_SUFFIXES
    )


def describe_cmdb_file(path: Path, root_path: Path) -> str:
    try:
        return path.relative_to(root_path).as_posix()
    except ValueError:
        return path.name


def list_cmdb_entity_files(root_path: Path, uuid_column: str, name_column: str) -> list[Path]:
    return [
        path
        for path in list_cmdb_files(root_path)
        if _csv_has_columns(path, {uuid_column, name_column})
    ]


def list_cmdb_relation_files(
    root_path: Path,
    source_id_column: str,
    relation_type_column: str,
    target_id_column: str,
) -> list[Path]:
    return [
        path
        for path in list_cmdb_files(root_path)
        if _csv_has_columns(path, {source_id_column, relation_type_column, target_id_column})
    ]


def _csv_has_columns(path: Path, required_columns: set[str]) -> bool:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return False
            return required_columns.issubset(set(reader.fieldnames))
    except (OSError, csv.Error, UnicodeDecodeError):
        return False
