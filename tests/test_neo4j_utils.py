import pytest
from neo4j.exceptions import AuthError, ClientError, CypherSyntaxError, DriverError, ServiceUnavailable

from core.neo4j_utils import (
    Neo4jAuthenticationError,
    Neo4jConnectionError,
    Neo4jQueryError,
    Neo4jQuerySyntaxError,
    Neo4jServiceUnavailableError,
    QueryValidationError,
    _translate_neo4j_exception,
    validate_read_only_cypher,
)


def test_validate_read_only_cypher_allows_simple_match() -> None:
    validate_read_only_cypher("MATCH (p:Process) RETURN p.name")


def test_validate_read_only_cypher_rejects_write_tokens() -> None:
    with pytest.raises(QueryValidationError):
        validate_read_only_cypher("MATCH (p) DELETE p")


def test_validate_read_only_cypher_allows_forbidden_tokens_inside_string_literals() -> None:
    validate_read_only_cypher('MATCH (p) RETURN "CREATE this" AS note')


def test_validate_read_only_cypher_allows_forbidden_tokens_inside_line_comments() -> None:
    validate_read_only_cypher("MATCH (p) // DELETE p\nRETURN p.name")


def test_validate_read_only_cypher_allows_forbidden_tokens_inside_block_comments() -> None:
    validate_read_only_cypher("MATCH (p) /* MERGE (x) */ RETURN p.name")


def test_validate_read_only_cypher_rejects_match_after_return_without_with() -> None:
    with pytest.raises(QueryValidationError, match="multiple statements"):
        validate_read_only_cypher(
            "MATCH (a:Application) RETURN count(a) AS applicationCount MATCH (p:Process) RETURN count(p) AS processCount"
        )


def test_validate_read_only_cypher_allows_with_between_return_and_match() -> None:
    validate_read_only_cypher(
        "MATCH (a:Application) WITH count(a) AS applicationCount MATCH (p:Process) RETURN applicationCount, count(p) AS processCount"
    )


def test_validate_read_only_cypher_rejects_union_with_different_return_aliases() -> None:
    with pytest.raises(QueryValidationError, match="same column aliases"):
        validate_read_only_cypher(
            "MATCH (a:Application) RETURN a.name AS application UNION ALL MATCH (p:Process) RETURN p.name AS process"
        )


def test_validate_read_only_cypher_allows_union_with_order_by_after_last_branch() -> None:
    validate_read_only_cypher(
        "MATCH (n:Process) RETURN 'Process' AS entity_type, n.name AS entity_name "
        "UNION ALL "
        "MATCH (n:Application) RETURN 'Application' AS entity_type, n.name AS entity_name "
        "ORDER BY entity_type, entity_name"
    )


def test_validate_read_only_cypher_rejects_unknown_relationship_type() -> None:
    with pytest.raises(QueryValidationError, match="unknown relationship type: HOSTET"):
        validate_read_only_cypher(
            "MATCH (s:Server)-[:HOSTET]->(a:Application) RETURN s.name AS server, a.name AS application"
        )


def test_validate_read_only_cypher_rejects_wrong_runs_on_direction() -> None:
    with pytest.raises(QueryValidationError, match="invalid direction or endpoint labels"):
        validate_read_only_cypher(
            "MATCH (s:Server)-[:RUNS_ON]->(a:Application) RETURN s.name AS server, a.name AS application"
        )


def test_validate_read_only_cypher_allows_reverse_traversal_for_runs_on() -> None:
    validate_read_only_cypher(
        "MATCH (s:Server)<-[:RUNS_ON]-(a:Application) RETURN s.name AS server, a.name AS application"
    )


def test_translate_neo4j_exception_maps_auth_errors() -> None:
    translated = _translate_neo4j_exception(AuthError("auth failed"))

    assert isinstance(translated, Neo4jAuthenticationError)


def test_translate_neo4j_exception_maps_service_unavailable() -> None:
    translated = _translate_neo4j_exception(ServiceUnavailable("service down"))

    assert isinstance(translated, Neo4jServiceUnavailableError)
    assert "service down" in str(translated)


def test_translate_neo4j_exception_maps_cypher_syntax_errors() -> None:
    translated = _translate_neo4j_exception(
        CypherSyntaxError("Neo.ClientError.Statement.SyntaxError", "bad syntax")
    )

    assert isinstance(translated, Neo4jQuerySyntaxError)
    assert "Cypher syntax error" in str(translated)


def test_translate_neo4j_exception_maps_client_errors() -> None:
    translated = _translate_neo4j_exception(
        ClientError("Neo.ClientError.Statement.SemanticError", "bad request")
    )

    assert isinstance(translated, Neo4jQueryError)
    assert "bad request" in str(translated)


def test_translate_neo4j_exception_maps_driver_errors() -> None:
    translated = _translate_neo4j_exception(DriverError("driver failed"))

    assert isinstance(translated, Neo4jConnectionError)
    assert "driver failed" in str(translated)


# --- graph_schema validation via validate_read_only_cypher ---

def test_validate_read_only_cypher_rejects_unknown_node_label() -> None:
    with pytest.raises(QueryValidationError, match="unknown node label"):
        validate_read_only_cypher("MATCH (d:Datenbank) RETURN d.name")


def test_validate_read_only_cypher_rejects_wrong_dient_direction() -> None:
    with pytest.raises(QueryValidationError, match="invalid direction or endpoint labels"):
        validate_read_only_cypher(
            "MATCH (p:Process)-[:SERVES]->(a:Application) RETURN p.name AS process, a.name AS application"
        )


def test_validate_read_only_cypher_allows_correct_dient_direction() -> None:
    validate_read_only_cypher(
        "MATCH (a:Application)-[:SERVES]->(p:Process) RETURN a.name AS application, p.name AS process"
    )


def test_validate_read_only_cypher_rejects_undirected_relationship() -> None:
    with pytest.raises(QueryValidationError):
        validate_read_only_cypher(
            "MATCH (a:Application)-[:SERVES]-(p:Process) RETURN a.name AS application"
        )


def test_validate_read_only_cypher_rejects_unknown_property_for_known_label() -> None:
    with pytest.raises(QueryValidationError, match="unknown property"):
        validate_read_only_cypher(
            "MATCH (p:Process) RETURN p.beschreibung AS description"
        )


def test_validate_read_only_cypher_allows_known_property_for_prozess() -> None:
    validate_read_only_cypher("MATCH (p:Process) RETURN p.name AS name, p.process_id AS id")


def test_validate_read_only_cypher_rejects_wrong_verantwortet_direction() -> None:
    with pytest.raises(QueryValidationError, match="invalid direction or endpoint labels"):
        validate_read_only_cypher(
            "MATCH (p:Process)-[:RESPONSIBLE_FOR]->(o:OrgUnit) RETURN p.name AS process"
        )
