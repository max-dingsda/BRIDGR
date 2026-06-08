from processing.query_layer import sanitize_cypher_response


def test_sanitize_cypher_response_strips_cypher_fence() -> None:
    raw = "```cypher\nMATCH (p:Prozess) RETURN p.name AS process_name\n```"
    assert sanitize_cypher_response(raw) == "MATCH (p:Prozess) RETURN p.name AS process_name"


def test_sanitize_cypher_response_strips_plain_fence() -> None:
    raw = "```\nMATCH (p:Prozess) RETURN p.name AS process_name\n```"
    assert sanitize_cypher_response(raw) == "MATCH (p:Prozess) RETURN p.name AS process_name"


def test_sanitize_cypher_response_returns_plain_query_unchanged() -> None:
    raw = "MATCH (p:Prozess) RETURN p.name AS process_name"
    assert sanitize_cypher_response(raw) == raw


def test_sanitize_cypher_response_strips_surrounding_whitespace() -> None:
    raw = "  MATCH (p:Prozess) RETURN p.name AS process_name  "
    assert sanitize_cypher_response(raw) == "MATCH (p:Prozess) RETURN p.name AS process_name"
