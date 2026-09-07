from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
from contextvars import ContextVar
import re
import json
import logging
from pathlib import Path
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
    password: str = field(repr=False)
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
        self._transaction = ContextVar(f"neo4j_transaction_{id(self)}", default=None)
        self._write_lock = ContextVar(f"neo4j_write_lock_{id(self)}", default=False)
        self._artifact_paths = ContextVar(f"neo4j_artifacts_{id(self)}", default=None)
        self._constraints_ready = False
        self._driver = GraphDatabase.driver(
            config.url,
            auth=(config.user, config.password),
            notifications_disabled_categories=["UNRECOGNIZED"],
        )

    def close(self) -> None:
        self._driver.close()

    def execute_write(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.transaction():
            return self._execute(query, parameters)

    @contextmanager
    def serialized_writes(self):
        """Serialize BRIDGR writers across clients/processes using a database lock.

        The lock transaction has no domain writes. Its node is operational runtime
        state and deliberately excluded from logical snapshots and restore.
        """
        if self._write_lock.get():
            yield self
            return
        self.ensure_constraints()
        with self._driver.session(database=self._database or None) as session:
            with session.begin_transaction(timeout=0) as lock:
                lock.run("MERGE (l:__BridgrWriteLock {id:'writer'}) SET l.held = true").consume()
                token = self._write_lock.set(True)
                try:
                    yield self
                finally:
                    self._write_lock.reset(token)
                    lock.rollback()

    @contextmanager
    def transaction(self):
        """Join the explicit unit of work on this client, or start one."""
        if self._transaction.get() is not None:
            yield self
            return
        with self.serialized_writes():
            self.publish_pending_artifacts(required_paths=set())
            artifact_paths = set()
            with self._driver.session(database=self._database or None) as session:
                with session.begin_transaction() as transaction:
                    token = self._transaction.set(transaction)
                    artifact_token = self._artifact_paths.set(artifact_paths)
                    try:
                        yield self
                        transaction.commit()
                    except BaseException:
                        transaction.rollback()
                        raise
                    finally:
                        self._transaction.reset(token)
                        self._artifact_paths.reset(artifact_token)
            self.publish_pending_artifacts(required_paths=artifact_paths)

    def stage_artifact(self, path: Path, payload: dict) -> None:
        """Persist a replayable JSON projection in the same transaction as its graph changes."""
        if self._transaction.get() is None:
            raise RuntimeError("Artifact staging requires an active transaction.")
        self._artifact_paths.get().add(str(path.resolve()))
        self._execute(
            "MERGE (a:__BridgrArtifact {path:$path}) SET a.payload = $payload",
            {"path": str(path.resolve()), "payload": json.dumps(payload, ensure_ascii=False)},
        )

    def read_staged_artifact(self, path: Path):
        rows = self._execute("MATCH (a:__BridgrArtifact {path:$path}) RETURN a.payload AS payload",
                             {"path": str(path.resolve())})
        return json.loads(rows[0]["payload"]) if rows else None

    def publish_pending_artifacts(self, required_paths=None) -> None:
        from processing.run_artifacts import atomic_write_json

        if self._transaction.get() is not None:
            return
        for row in self._execute("MATCH (a:__BridgrArtifact) RETURN a.path AS path, a.payload AS payload"):
            try:
                atomic_write_json(Path(row["path"]), json.loads(row["payload"]))
                self._execute("MATCH (a:__BridgrArtifact {path:$path}) DELETE a", {"path": row["path"]})
            except Exception as exc:
                logging.getLogger(__name__).exception("Artifact publication failed for %s", row["path"])
                if required_paths is None or row["path"] in required_paths:
                    raise Neo4jExecutionError(
                        "Graph wurde gespeichert; Anzeige ist noch ausstehend. "
                        "Die gespeicherte Aktualisierung wird beim nächsten Schreibvorgang erneut veröffentlicht."
                    ) from exc

    def execute_write_batch(self, statements: list[tuple[str, dict[str, Any]]]) -> list[list[dict[str, Any]]]:
        """Execute all write statements in one Neo4j transaction."""
        try:
            with self.transaction():
                return [self._execute(query, parameters) for query, parameters in statements]
        except Exception as exc:
            raise _translate_neo4j_exception(exc) from exc

    def execute_read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        validate_read_only_cypher(query)
        return self._execute(query, parameters)

    def execute_read_unvalidated(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._execute(query, parameters)

    def ensure_constraints(self) -> None:
        if self._constraints_ready:
            return
        constraint_queries = [
            "CREATE CONSTRAINT bridgr_identity IF NOT EXISTS FOR (n:__BridgrIdentity) REQUIRE n.__bridgr_id IS UNIQUE",
            "CREATE CONSTRAINT bridgr_artifact_path IF NOT EXISTS FOR (a:__BridgrArtifact) REQUIRE a.path IS UNIQUE",
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
        self._execute("CREATE CONSTRAINT bridgr_write_lock IF NOT EXISTS FOR (l:__BridgrWriteLock) REQUIRE l.id IS UNIQUE")
        self._execute("MERGE (:__BridgrWriteLock {id:'writer'})")
        self._constraints_ready = True

    def _execute(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            transaction = self._transaction.get()
            if transaction is not None:
                return [record.data() for record in transaction.run(query, parameters or {})]
            session_kwargs = {"database": self._database} if self._database else {}
            with self._driver.session(**session_kwargs) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as exc:
            raise _translate_neo4j_exception(exc) from exc


def _translate_neo4j_exception(exc: Exception) -> Neo4jExecutionError:
    if isinstance(exc, Neo4jExecutionError):
        return exc
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
    from core.chat_cypher import validate_chat_cypher
    cleaned_query = _strip_cypher_strings_and_comments(query)
    normalized_query = " ".join(cleaned_query.upper().split())
    if not normalized_query:
        raise QueryValidationError("Cypher query is empty.")
    for token in READ_ONLY_FORBIDDEN_TOKENS:
        if re.search(r"\b" + re.escape(token) + r"\b", normalized_query):
            raise QueryValidationError(f"Cypher query contains forbidden token: {token}")
    _validate_query_structure(normalized_query)
    try:
        validate_chat_cypher(query)
    except ValueError as exc:
        raise QueryValidationError(str(exc)) from exc


def _validate_query_structure(normalized_query: str) -> None:
    if _has_match_after_return_without_transition(normalized_query):
        raise QueryValidationError(
            "Cypher query appears to contain multiple statements. Use a single query and continue after RETURN only with UNION, "
            "or move intermediate results with WITH."
        )


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
