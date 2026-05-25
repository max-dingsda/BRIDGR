from __future__ import annotations

import csv
from pathlib import Path


class CmdbLoadError(RuntimeError):
    pass


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
