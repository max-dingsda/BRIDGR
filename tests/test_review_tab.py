from app_config import AppConfig
from ui.review_tab import _filter_application_cmdb_rows


def test_filter_application_cmdb_rows_keeps_only_applications() -> None:
    config = AppConfig(cmdb_entity_type_column="entity_type")

    rows = [
        {"id": "app-1", "name": "Seller Service", "entity_type": "application"},
        {"id": "if-1", "name": "Seller Service API", "entity_type": "interface"},
        {"id": "srv-1", "name": "vm-app-01", "entity_type": "server"},
        {"id": "legacy-1", "name": "Legacy App"},
    ]

    filtered = _filter_application_cmdb_rows(config, rows)

    assert filtered == [
        {"id": "app-1", "name": "Seller Service", "entity_type": "application"},
        {"id": "legacy-1", "name": "Legacy App"},
    ]
