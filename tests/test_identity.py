import pytest
from xml.etree.ElementTree import ParseError

from skills.identity import extract_bpmn_process_ids


def test_extract_bpmn_process_ids_returns_all_process_ids() -> None:
    xml_text = """
    <definitions xmlns="http://example.com/bpmn">
      <process id="order_flow" />
      <process id="invoice_flow" />
    </definitions>
    """

    assert extract_bpmn_process_ids(xml_text) == ["order_flow", "invoice_flow"]


def test_extract_bpmn_process_ids_returns_empty_list_when_no_processes() -> None:
    xml_text = "<definitions />"

    assert extract_bpmn_process_ids(xml_text) == []


def test_extract_bpmn_process_ids_raises_for_malformed_xml() -> None:
    with pytest.raises(ParseError):
        extract_bpmn_process_ids("<definitions>")

