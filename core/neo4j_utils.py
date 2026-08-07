from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from core.graph_schema import validate_query_schema


class Neo4jExecutionError(RuntimeError):
    pass


class Neo4jConnectionError(Neo4jExecutionError):
    pass


class Neo4jAuthenticationError(Neo4jConnectionError):
    pass


class Neo4jServiceUnavailableError(Neo4jConnectionError):
    pass


class Neo4jQueryError(Neo4jExecutionError):
    pass


class Neo4jQuerySyntaxError(Neo4jQueryError):
    pass


class QueryValidationError(RuntimeError):
    pass


READ_ONLY_FORBIDDEN_TOKENS = [
    "CREATE",
    "MERGE",
    "DELETE",
    "DETACH",
    "SET",
    "REMOVE",
    "DROP",
    "LOAD CSV",
    "CALL DBMS",
    "CALL APOC",
]


@dataclass(slots=True)
class Neo4jConfig:
    url: str
    user: str
    password: str
    database: str = ""


class Neo4jClient:
    def __init__(self, config: Neo4jConfig) -> None:
        try:
            from neo4j import GraphDatabase
        except ModuleNotFoundError as exc:
            raise Neo4jConnectionError(
                "Neo4j driver is not installed. Please run `python -m pip install -r requirements-dev.txt`."
            ) from exc

        self._database = config.database
        self._driver = GraphDatabase.driver(
            config.url,
            auth=(config.user, config.password),
            notifications_disabled_categories=["UNRECOGNIZED"],
        )

    def close(self) -> None:
        self._driver.close()

    def execute_write(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._execute(query, parameters)

    def execute_write_batch(self, statements: list[tuple[str, dict[str, Any]]]) -> list[list[dict[str, Any]]]:
        """Execute all write statements in one Neo4j transaction."""
        try:
            session_kwargs = {"database": self._database} if self._database else {}
            with self._driver.session(**session_kwargs) as session:
                with session.begin_transaction() as transaction:
                    results = [
                        [record.data() for record in transaction.run(query, parameters)]
                        for query, parameters in statements
                    ]
                    transaction.commit()
                    return results
        except Exception as exc:
            raise _translate_neo4j_exception(exc) from exc

    def execute_read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        validate_read_only_cypher(query)
        return self._execute(query, parameters)

    def execute_read_unvalidated(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._execute(query, parameters)

    def ensure_constraints(self) -> None:
        constraint_queries = [
            "CREATE CONSTRAINT process_id IF NOT EXISTS FOR (p:Process) REQUIRE p.process_id IS UNIQUE",
            "CREATE CONSTRAINT anwendung_id IF NOT EXISTS FOR (a:Application) REQUIRE a.cmdb_id IS UNIQUE",
            "CREATE CONSTRAINT schnittstelle_id IF NOT EXISTS FOR (i:Interface) REQUIRE i.id IS UNIQUE",
            "CREATE CONSTRAINT server_id IF NOT EXISTS FOR (s:Server) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT orgeinheit_name IF NOT EXISTS FOR (o:OrgUnit) REQUIRE o.name IS UNIQUE",
            "CREATE CONSTRAINT alias_normalized_name IF NOT EXISTS FOR (a:Alias) REQUIRE a.normalized_name IS UNIQUE",
            "CREATE CONSTRAINT org_kandidat_normalized_name IF NOT EXISTS FOR (k:OrgCandidate) REQUIRE k.normalized_name IS UNIQUE",
        ]
        for query in constraint_queries:
            self._execute(query, {})

    def _execute(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            session_kwargs = {"database": self._database} if self._database else {}
            with self._driver.session(**session_kwargs) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as exc:
            raise _translate_neo4j_exception(exc) from exc


def _translate_neo4j_exception(exc: Exception) -> Neo4jExecutionError:
    try:
        from neo4j.exceptions import AuthError, ClientError, CypherSyntaxError, DriverError, ServiceUnavailable, SessionExpired
    except ModuleNotFoundError:
        return Neo4jConnectionError(str(exc))

    if isinstance(exc, AuthError):
        return Neo4jAuthenticationError(
            "Neo4j authentication failed. Please verify URL, username, password, and database access."
        )
    if isinstance(exc, (ServiceUnavailable, SessionExpired)):
        return Neo4jServiceUnavailableError(f"Neo4j is currently unavailable: {exc}")
    if isinstance(exc, CypherSyntaxError):
        return Neo4jQuerySyntaxError(f"Cypher syntax error: {exc}")
    if isinstance(exc, ClientError):
        return Neo4jQueryError(f"Neo4j rejected the query: {exc}")
    if isinstance(exc, DriverError):
        return Neo4jConnectionError(f"Neo4j driver error: {exc}")
    return Neo4jConnectionError(str(exc))


def validate_read_only_cypher(query: str) -> None:
    cleaned_query = _strip_cypher_strings_and_comments(query)
    normalized_query = " ".join(cleaned_query.upper().split())
    if not normalized_query:
        raise QueryValidationError("Cypher query is empty.")
    for token in READ_ONLY_FORBIDDEN_TOKENS:
        if token in normalized_query:
            raise QueryValidationError(f"Cypher query contains forbidden token: {token}")
    _validate_query_structure(normalized_query)
    try:
        validate_query_schema(cleaned_query)
    except ValueError as exc:
        raise QueryValidationError(str(exc)) from exc


def _validate_query_structure(normalized_query: str) -> None:
    if _has_match_after_return_without_transition(normalized_query):
        raise QueryValidationError(
            "Cypher query appears to contain multiple statements. Use a single query and continue after RETURN only with UNION, "
            "or move intermediate results with WITH."
        )
    if "UNION" in normalized_query:
        _validate_union_return_columns(normalized_query)


def _has_match_after_return_without_transition(normalized_query: str) -> bool:
    tokens = normalized_query.split()
    seen_return = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        combined_token = f"{token} {next_token}".strip()

        if token == "RETURN":
            seen_return = True
            index += 1
            continue
        if token == "WITH":
            seen_return = False
        elif token == "UNION":
            seen_return = False
        elif seen_return and (token == "MATCH" or combined_token == "OPTIONAL MATCH"):
            return True
        index += 1
    return False


def _validate_union_return_columns(normalized_query: str) -> None:
    branches = [branch.strip() for branch in re.split(r"\bUNION(?: ALL)?\b", normalized_query) if branch.strip()]
    if len(branches) < 2:
        return

    expected_aliases = _extract_return_aliases(branches[0])
    if not expected_aliases:
        return

    for branch in branches[1:]:
        branch_aliases = _extract_return_aliases(branch)
        if branch_aliases != expected_aliases:
            raise QueryValidationError(
                "Cypher UNION branches must return the same column aliases in the same order."
            )


def _extract_return_aliases(branch: str) -> list[str]:
    return_match = re.search(r"\bRETURN\b\s+(.+)$", branch)
    if return_match is None:
        return []

    return_clause = re.split(r"\bORDER BY\b|\bSKIP\b|\bLIMIT\b", return_match.group(1), maxsplit=1)[0]
    aliases: list[str] = []
    for item in return_clause.split(","):
        normalized_item = item.strip()
        alias_match = re.search(r"\bAS\s+([A-Z_][A-Z0-9_]*)$", normalized_item)
        if alias_match is not None:
            aliases.append(alias_match.group(1))
            continue
        bare_identifier_match = re.search(r"([A-Z_][A-Z0-9_]*)$", normalized_item)
        if bare_identifier_match is not None:
            aliases.append(bare_identifier_match.group(1))
    return aliases


def _strip_cypher_strings_and_comments(query: str) -> str:
    result: list[str] = []
    index = 0
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False

    while index < len(query):
        current = query[index]
        next_char = query[index + 1] if index + 1 < len(query) else ""

        if in_line_comment:
            if current == "\n":
                in_line_comment = False
                result.append(current)
            index += 1
            continue

        if in_block_comment:
            if current == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            index += 1
            continue

        if in_single_quote:
            if current == "\\" and next_char:
                index += 2
                continue
            if current == "'":
                in_single_quote = False
            index += 1
            continue

        if in_double_quote:
            if current == "\\" and next_char:
                index += 2
                continue
            if current == '"':
                in_double_quote = False
            index += 1
            continue

        if current == "/" and next_char == "/":
            in_line_comment = True
            index += 2
            continue

        if current == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue

        if current == "'":
            in_single_quote = True
            index += 1
            continue

        if current == '"':
            in_double_quote = True
            index += 1
            continue

        result.append(current)
        index += 1

    return "".join(result)
