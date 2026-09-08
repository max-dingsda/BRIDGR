from core.app_config import AppConfig
from services.cmdb_service import load_application_cmdb_rows
from ui import review_tab


def test_load_application_cmdb_rows_returns_empty_when_no_type_files_configured() -> None:
    config = AppConfig(cmdb_type_files={})
    rows = load_application_cmdb_rows(config)
    assert rows == []


def test_review_row_checkbox_has_accessible_label(monkeypatch) -> None:
    checkbox_calls = []

    class ColumnStub:
        def checkbox(self, label, **kwargs):
            checkbox_calls.append((label, kwargs))
            return False

        def write(self, _value):
            return None

        def button(self, _label, **_kwargs):
            return False

    monkeypatch.setattr(review_tab.st, "columns", lambda _widths: [ColumnStub() for _ in range(8)])
    monkeypatch.setattr(review_tab, "load_application_cmdb_rows", lambda _config: [])
    monkeypatch.setattr(review_tab, "get_active_locale", lambda: "en")

    review_tab.render_review_item_actions(
        {
            "process": "Invoice",
            "process_id": "process-1",
            "source_path": "Input/invoice.txt",
            "anwendung_im_prozess": "Billing",
            "anwendung_in_cmdb": "Billing System",
            "cmdb_id": "app-1",
            "row_id": "row-1",
            "confidence": "weak",
        },
        AppConfig(),
        [],
    )

    assert len(checkbox_calls) == 1
    label, options = checkbox_calls[0]
    assert label == "Select mapping for Billing in process Invoice"
    assert options["key"] == "review-batch-select::row-1"
    assert options["label_visibility"] == "collapsed"
