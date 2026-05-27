from skills.extract.extract_base import ApplicationReference, ExtractedProcess
from skills.graph_writer import GraphWriter, GraphWritePayload
from skills.match import MatchResult


class RecordingNeo4jClient:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict | None]] = []

    def ensure_constraints(self) -> None:
        self.queries.append(("ENSURE_CONSTRAINTS", None))

    def execute_write(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        return []


def test_graph_writer_removes_existing_process_application_links_before_rewrite() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Incident Management",
            process_id="WFP-1-1",
            org_unit="Support",
            roles=["Support"],
            org_units=["Support"],
            org_unit_candidates=[],
            follows_after=[],
            raw_applications=[ApplicationReference(name="Mail", confidence="schwach")],
            applications=[ApplicationReference(name="Mail", confidence="schwach")],
            source_path="Input/process.xml",
        ),
        matches=[
            MatchResult(
                application_name="Mail",
                cmdb_id="cmdb-1",
                matched_name="Mail System",
                confidence="schwach",
                source="fuzzy",
            )
        ],
    )

    writer.write_payload(client, payload)

    queries = [query for query, _ in client.queries]
    assert any("DELETE r" in query for query in queries)
    assert not any("MERGE (p)-[r:NUTZT]->(a)" in query for query in queries)


def test_graph_writer_only_writes_strong_or_confirmed_matches() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Incident Management",
            process_id="WFP-1-1",
            org_unit="Support",
            roles=["Support"],
            org_units=["Support"],
            org_unit_candidates=[],
            follows_after=[],
            raw_applications=[
                ApplicationReference(name="Ticket", confidence="stark"),
                ApplicationReference(name="Mail", confidence="schwach"),
            ],
            applications=[
                ApplicationReference(name="Ticket", confidence="stark"),
                ApplicationReference(name="Mail", confidence="schwach"),
            ],
            source_path="Input/process.xml",
        ),
        matches=[
            MatchResult(
                application_name="Ticket",
                cmdb_id="cmdb-1",
                matched_name="Trouble Ticket System",
                confidence="stark",
                source="fuzzy",
            ),
            MatchResult(
                application_name="Mail",
                cmdb_id="cmdb-2",
                matched_name="Mail System",
                confidence="schwach",
                source="fuzzy",
            ),
            MatchResult(
                application_name="Manual Mail",
                cmdb_id="cmdb-3",
                matched_name="Manual Mail System",
                confidence="schwach",
                source="knowledge_base_manual",
            ),
        ],
    )

    writer.write_payload(client, payload)

    nutz_writes = [
        parameters
        for query, parameters in client.queries
        if "MERGE (p)-[r:NUTZT]->(a)" in query
    ]
    written_cmdb_ids = {entry["cmdb_id"] for entry in nutz_writes}

    assert written_cmdb_ids == {"cmdb-1", "cmdb-3"}
