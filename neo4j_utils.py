from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        self._driver = GraphDatabase.driver(config.url, auth=(config.user, config.password))

    def close(self) -> None:
        self._driver.close()

    def execute_write(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._execute(query, parameters)

    def execute_read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        validate_read_only_cypher(query)
        return self._execute(query, parameters)

    def ensure_constraints(self) -> None:
        constraint_queries = [
            "CREATE CONSTRAINT prozess_id IF NOT EXISTS FOR (p:Prozess) REQUIRE p.prozess_id IS UNIQUE",
            "CREATE CONSTRAINT anwendung_id IF NOT EXISTS FOR (a:Anwendung) REQUIRE a.cmdb_id IS UNIQUE",
            "CREATE CONSTRAINT orgeinheit_name IF NOT EXISTS FOR (o:OrgEinheit) REQUIRE o.name IS UNIQUE",
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
    normalized_query = " ".join(_strip_cypher_strings_and_comments(query).upper().split())
    if not normalized_query:
        raise QueryValidationError("Cypher query is empty.")
    for token in READ_ONLY_FORBIDDEN_TOKENS:
        if token in normalized_query:
            raise QueryValidationError(f"Cypher query contains forbidden token: {token}")


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
