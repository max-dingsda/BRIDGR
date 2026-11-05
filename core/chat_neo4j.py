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
        return self._execute_read(query, parameters)

    def execute_visualization_read(self, query: str, parameters=None):
        """Run one of the fixed, application-owned diagram lookups.

        The normal validator intentionally rejects unlabelled patterns so LLM
        output cannot widen its scope.  The diagram companion uses three fixed
        read-only queries with those patterns; they are not LLM-authored and this
        method only accepts their exact shapes.
        """
        if not _is_fixed_visualization_query(query):
            raise QueryValidationError("Unsupported visualization query.")
        return self._execute_read(query, parameters)

    def _execute_read(self, query: str, parameters=None):
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


def _is_fixed_visualization_query(query: str) -> bool:
    """Allow only the deterministic queries defined in graph_view_service."""
    normalized = " ".join(query.split())
    return normalized in {
        "MATCH (n) WHERE n.name = $value AND any(l IN labels(n) WHERE l IN $visual_labels) "
        "RETURN elementId(n) AS eid, [l IN labels(n) WHERE l IN $visual_labels][0] AS label",
        "MATCH (n)-[r]-(m) WHERE elementId(n) IN $element_ids AND type(r) IN $relationship_types "
        "AND any(l IN labels(m) WHERE l IN $visual_labels) RETURN elementId(n) AS source_eid, "
        "elementId(m) AS target_eid, type(r) AS relationship_type, startNode(r) = n AS outgoing, "
        "[l IN labels(m) WHERE l IN $visual_labels][0] AS target_label, m.name AS target_name",
        "MATCH (a)-[r:MAY_SERVE]->(b) WHERE elementId(a) IN $element_ids AND elementId(b) IN $element_ids "
        "RETURN elementId(a) AS source_eid, elementId(b) AS target_eid, type(r) AS relationship_type",
        "MATCH (a)-[r]->(b) WHERE elementId(a) IN $element_ids AND elementId(b) IN $element_ids "
        "AND type(r) IN $relationship_types RETURN elementId(a) AS source_eid, elementId(b) AS target_eid, "
        "type(r) AS relationship_type",
    }
