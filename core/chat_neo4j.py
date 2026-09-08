"""Read-only chat boundary, separate from the application's write client."""
import json

from neo4j import GraphDatabase, Query, READ_ACCESS

from core.neo4j_utils import Neo4jConfig, Neo4jConnectionError, QueryValidationError, validate_read_only_cypher, _translate_neo4j_exception


class ChatConfigurationError(Neo4jConnectionError):
    pass


class ChatNeo4jClient:
    def __init__(self, config: Neo4jConfig):
        if not config.user or not config.password or not config.database:
            raise ChatConfigurationError("Configure a dedicated read-only chat account and an explicit database.")
        self._database = config.database
        self._driver = GraphDatabase.driver(config.url, auth=(config.user, config.password))

    def close(self):
        self._driver.close()

    def _verify_read_only(self):
        # Roles can be customized: inspect effective grants, not just role names.
        allowed = {"access", "match", "read", "traverse", "show_index", "show_constraint",
                   "execute", "execute_function", "load"}
        with self._driver.session(database="system", default_access_mode=READ_ACCESS) as session:
            privileges = session.run(Query("SHOW USER PRIVILEGES", timeout=15)).data()
        if not privileges or any(row.get("access") == "GRANTED" and row.get("action") not in allowed
                                 for row in privileges):
            raise ChatConfigurationError("Chat account has write/administration or unsupported privileges; use a read-only account.")

    def execute_read(self, query: str, parameters=None):
        validate_read_only_cypher(query)
        try:
            self._verify_read_only()
            with self._driver.session(database=self._database, default_access_mode=READ_ACCESS) as session:
                result = session.run(Query(query, timeout=15), parameters or {})
                rows = []
                size = 0
                for record in result:
                    row = record.data()
                    size += len(json.dumps(row, ensure_ascii=False, default=str))
                    if len(rows) >= 500 or size > 100000:
                        raise QueryValidationError("Query result exceeds the chat budget; narrow or aggregate the query.")
                    rows.append(row)
                return rows
        except (QueryValidationError, Neo4jConnectionError):
            raise
        except Exception as exc:
            raise _translate_neo4j_exception(exc) from exc
