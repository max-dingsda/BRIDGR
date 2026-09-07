import pytest

from core.neo4j_utils import QueryValidationError, validate_read_only_cypher


@pytest.mark.parametrize("query", [
    "MATCH (n) RETURN labels(n), properties(n) LIMIT 1",
    "MATCH (n) WHERE n:ManualDecision RETURN n.payload_json LIMIT 1",
    "MATCH (:ManualDecision) RETURN count(*)",
    "MATCH (p:Process) RETURN p",
    "MATCH (p:Process) WITH p AS n RETURN n",
    "MATCH (p:Process) RETURN collect(p)",
    "MATCH (p:Process) RETURN p{.*}",
    "MATCH (p:Process) RETURN p['payload_json']",
    "MATCH (p:Process) RETURN properties(p)",
    "MATCH (p:Process) RETURN p.name UNION MATCH (n) RETURN n.payload_json",
    "MATCH (p:Process) WITH p.name AS x MATCH (n) RETURN x",
    "MATCH (p:Process) WHERE EXISTS { MATCH (n:ManualDecision) } RETURN p.name",
    "MATCH (p:Process)-[:FOLLOWS*1..3]->(q:Process) RETURN q.name",
    "MATCH (p:Process)-[r]->(q:Process) RETURN type(r)",
    "MATCH (p:Process) CALL db.labels() YIELD label RETURN label",
    "MATCH (p:Process) RETURN apoc.text.join([p.name], ',')",
    "MATCH (p:Process:ManualDecision) RETURN p.name",
    "MATCH (`p`:Process) RETURN `p`.name",
    "MATCH (p:Process) RETURN p.name; RETURN 1",
    "MATCH (p:Process) RETURN p.name /* unterminated",
])
def test_chat_rejects_unproven_data_access(query):
    with pytest.raises(QueryValidationError):
        validate_read_only_cypher(query)


@pytest.mark.parametrize("query", [
    "MATCH (:Process) RETURN count(*) AS total",
    "MATCH (p:Process) WHERE toLower(p.name) CONTAINS 'order' RETURN p.name",
    "MATCH (p:Process) OPTIONAL MATCH (o:OrgUnit)-[:RESPONSIBLE_FOR]->(p) WHERE o IS NULL RETURN p.name",
    "MATCH (p:Process) WHERE NOT (:OrgUnit)-[:RESPONSIBLE_FOR]->(p) RETURN p.name",
    "MATCH (a:Application)-[r:SERVES]->(p:Process) RETURN a.name, p.name, r.source",
    "MATCH (a:Application)-[:SERVES]->(p:Process) WITH p, count(a) AS total WHERE total > 1 RETURN p.name, total ORDER BY total DESC LIMIT 10",
    "MATCH (p:Process) RETURN CASE WHEN p.name IS NULL THEN 'missing' ELSE p.name END AS name",
    "MATCH (p:Process) RETURN collect(p.name) AS names",
    "MATCH (p:Process) RETURN p.name AS name UNION ALL MATCH (a:Application) RETURN a.name AS name ORDER BY name",
])
def test_chat_allows_domain_questions(query):
    validate_read_only_cypher(query)
