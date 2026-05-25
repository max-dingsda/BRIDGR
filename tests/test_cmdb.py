from pathlib import Path

import pytest

from cmdb import CmdbLoadError, load_cmdb_rows


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
