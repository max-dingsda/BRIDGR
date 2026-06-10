from neo4j import GraphDatabase


URI = "neo4j://127.0.0.1:7687"
AUTH = ("bridgragent", "bridgragent")
DATABASE = "bridgr-architecture"
NAMES = [
    "t1 -> t2",
    "t2 -> t3",
    "t3 -> t4",
    "t4 -> t5",
    "t5 -> t7",
    "t6 -> Ende",
    "t7 -> t6",
]


DETAIL_QUERY = """
MATCH (p:Prozess)
WHERE p.name IN $names
RETURN p.name AS process, p.prozess_id AS process_id, p.placeholder AS placeholder
ORDER BY process
"""


LINK_QUERY = """
MATCH (p:Prozess)
WHERE p.name IN $names
OPTIONAL MATCH (curr:Prozess)-[:FOLGT_AUF]->(p)
OPTIONAL MATCH (p)-[:FOLGT_AUF]->(prev:Prozess)
RETURN p.name AS process,
       collect(DISTINCT curr.name) AS incoming_from,
       collect(DISTINCT prev.name) AS points_to
ORDER BY process
"""

PLACEHOLDER_SUMMARY_QUERY = """
MATCH (p:Prozess {placeholder: true})
RETURN count(p) AS placeholder_count, collect(p.name) AS placeholder_names
"""


ROOT_PROCESS_QUERY = """
MATCH (p:Prozess {name: 'Änderungsmanagement'})
RETURN p.name AS process, p.prozess_id AS process_id, p.placeholder AS placeholder
"""


def main() -> None:
    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        with driver.session(database=DATABASE) as session:
            detail_rows = [row.data() for row in session.run(DETAIL_QUERY, names=NAMES)]
            link_rows = [row.data() for row in session.run(LINK_QUERY, names=NAMES)]
            placeholder_summary = [row.data() for row in session.run(PLACEHOLDER_SUMMARY_QUERY)]
            root_process_rows = [row.data() for row in session.run(ROOT_PROCESS_QUERY)]
    finally:
        driver.close()

    print("DETAIL_ROWS")
    print(detail_rows)
    print("LINK_ROWS")
    print(link_rows)
    print("PLACEHOLDER_SUMMARY")
    print(placeholder_summary)
    print("ROOT_PROCESS_ROWS")
    print(root_process_rows)


if __name__ == "__main__":
    main()
