from skills.identity import extract_bpmn_process_ids


def test_extract_bpmn_process_ids_returns_all_process_ids() -> None:
    xml_text = """
    <definitions xmlns="http://example.com/bpmn">
      <process id="order_flow" />
      <process id="invoice_flow" />
    </definitions>
    """

    assert extract_bpmn_process_ids(xml_text) == ["order_flow", "invoice_flow"]

