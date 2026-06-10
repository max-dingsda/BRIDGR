from neo4j import GraphDatabase


URI = "neo4j://127.0.0.1:7687"
AUTH = ("bridgragent", "bridgragent")
DATABASE = "bridgr-architecture"

RISK_QUERY = """
MATCH (p:Prozess)
WITH count(CASE WHEN NOT EXISTS { (:OrgEinheit)-[:VERANTWORTET]->(p) } THEN 1 END) AS ownerless_process_count
MATCH (a:Anwendung)
WITH ownerless_process_count,
     count(CASE WHEN NOT EXISTS { (:OrgEinheit)-[:VERANTWORTET]->(a) } THEN 1 END) AS ownerless_application_count
MATCH (i:Schnittstelle)
WITH ownerless_process_count, ownerless_application_count,
     count(CASE WHEN NOT EXISTS { (:OrgEinheit)-[:VERANTWORTET]->(i) } THEN 1 END) AS ownerless_interface_count
MATCH (s:Server)
WITH ownerless_process_count, ownerless_application_count, ownerless_interface_count,
     count(CASE WHEN NOT EXISTS { (:OrgEinheit)-[:VERANTWORTET]->(s) } THEN 1 END) AS ownerless_server_count
MATCH (a:Anwendung)-[:RUNS_ON]->(s:Server)
WITH ownerless_process_count, ownerless_application_count, ownerless_interface_count, ownerless_server_count,
     s.name AS server, count(DISTINCT a) AS application_count
ORDER BY application_count DESC, server
RETURN ownerless_process_count, ownerless_application_count, ownerless_interface_count,
       ownerless_server_count, server, application_count
LIMIT 5
"""

FOLLOW_UP_QUERY = """
MATCH (p:Prozess)
WHERE NOT EXISTS { (:OrgEinheit)-[:VERANTWORTET]->(p) }
RETURN DISTINCT p.name AS process, p.prozess_id AS process_id, p.placeholder AS placeholder
ORDER BY process
"""


def main() -> None:
    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        with driver.session(database=DATABASE) as session:
            risk_rows = [row.data() for row in session.run(RISK_QUERY)]
            follow_up_rows = [row.data() for row in session.run(FOLLOW_UP_QUERY)]
    finally:
        driver.close()

    print("RISK_ROWS")
    print(risk_rows)
    print("FOLLOW_UP_ROWS")
    print(follow_up_rows)


if __name__ == "__main__":
    main()
