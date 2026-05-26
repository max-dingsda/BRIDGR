import pytest
from neo4j.exceptions import AuthError, ClientError, CypherSyntaxError, DriverError, ServiceUnavailable

from neo4j_utils import (
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
    validate_read_only_cypher("MATCH (p:Prozess) RETURN p.name")


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
            "MATCH (a:Anwendung) RETURN count(a) AS applicationCount MATCH (p:Prozess) RETURN count(p) AS processCount"
        )


def test_validate_read_only_cypher_allows_with_between_return_and_match() -> None:
    validate_read_only_cypher(
        "MATCH (a:Anwendung) WITH count(a) AS applicationCount MATCH (p:Prozess) RETURN applicationCount, count(p) AS processCount"
    )


def test_validate_read_only_cypher_rejects_union_with_different_return_aliases() -> None:
    with pytest.raises(QueryValidationError, match="same column aliases"):
        validate_read_only_cypher(
            "MATCH (a:Anwendung) RETURN a.name AS application UNION ALL MATCH (p:Prozess) RETURN p.name AS process"
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
