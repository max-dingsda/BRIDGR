from __future__ import annotations

import csv
from pathlib import Path


def load_cmdb_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


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
