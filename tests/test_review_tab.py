from core.app_config import AppConfig
from services.cmdb_service import load_application_cmdb_rows


def test_load_application_cmdb_rows_returns_empty_when_no_type_files_configured() -> None:
    config = AppConfig(cmdb_type_files={})
    rows = load_application_cmdb_rows(config)
    assert rows == []
