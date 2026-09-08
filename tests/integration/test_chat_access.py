import pytest
from neo4j.exceptions import ClientError

from core.neo4j_utils import QueryValidationError, Neo4jConfig, Neo4jConnectionError
from core.chat_neo4j import ChatNeo4jClient
from services.alias_service import lookup_alias_matches


def test_reader_can_query_domain_but_not_internal_nodes(graph_client, chat_client):
    graph_client.execute_write("""
        CREATE (:Process {process_id:'p1', name:'Order'})
        CREATE (:ManualDecision {payload_json:'private audit'})
        CREATE (:OrgCandidate {name:'private candidate'})
        CREATE (:Rejection {name:'private rejection'})
    """)
    assert chat_client.execute_read("MATCH (p:Process) RETURN p.name AS name") == [{"name": "Order"}]
    for query in ("MATCH (n) RETURN properties(n)", "MATCH (:ManualDecision) RETURN count(*)",
                  "MATCH (n) WHERE n:ManualDecision RETURN n.payload_json"):
        with pytest.raises(QueryValidationError):
            chat_client.execute_read(query)
    with chat_client._driver.session(database=chat_client._database) as session:
        with pytest.raises(ClientError):
            session.run("CREATE (:Process {name:'Must not be created'})").consume()


def test_chat_rejects_admin_credentials(isolated_neo4j_config):
    config = isolated_neo4j_config
    client = ChatNeo4jClient(Neo4jConfig(config.neo4j_url, config.neo4j_user,
                                       config.neo4j_password, config.neo4j_database))
    try:
        with pytest.raises(Neo4jConnectionError, match="privileges"):
            client.execute_read("RETURN 1 AS ok")
    finally:
        client.close()


def test_alias_hints_use_the_same_validated_boundary(graph_client, chat_client):
    graph_client.execute_write("""
        CREATE (a:Alias {name:'SAP', normalized_name:'sap'})
        CREATE (p:Application {name:'ERP', cmdb_id:'a1'})
        CREATE (private:ManualDecision {name:'Secret', payload_json:'private'})
        CREATE (a)-[:MAY_REFER_TO]->(p)
        CREATE (a)-[:MAY_REFER_TO]->(private)
    """)
    assert lookup_alias_matches(chat_client, "SAP") == [
        {"entity_type": "Application", "entity_name": "ERP", "entity_id": "a1", "alias_name": "SAP"}]
