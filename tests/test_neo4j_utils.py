import pytest

from neo4j_utils import QueryValidationError, validate_read_only_cypher


def test_validate_read_only_cypher_allows_simple_match() -> None:
    validate_read_only_cypher("MATCH (p:Prozess) RETURN p.name")


def test_validate_read_only_cypher_rejects_write_tokens() -> None:
    with pytest.raises(QueryValidationError):
        validate_read_only_cypher("MATCH (p) DELETE p")
