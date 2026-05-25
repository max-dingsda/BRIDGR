from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class Neo4jConnectionError(RuntimeError):
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
            raise Neo4jConnectionError(str(exc)) from exc


def validate_read_only_cypher(query: str) -> None:
    normalized_query = " ".join(query.upper().split())
    if not normalized_query:
        raise QueryValidationError("Cypher query is empty.")
    for token in READ_ONLY_FORBIDDEN_TOKENS:
        if token in normalized_query:
            raise QueryValidationError(f"Cypher query contains forbidden token: {token}")
