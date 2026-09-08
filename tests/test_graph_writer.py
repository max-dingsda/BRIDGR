from processing.cmdb import CmdbEntity, CmdbRelation, NormalizedCmdb
from skills.extract.extract_base import ApplicationReference, ExtractedProcess
from skills.graph_writer import GraphWriter, GraphWritePayload
from skills.match import MatchResult


class RecordingNeo4jClient:
    def __init__(self, read_response: list[dict] | None = None) -> None:
        self.queries: list[tuple[str, dict | None]] = []
        self.responses: list[list[dict]] = []
        self._read_response = read_response or []

    def ensure_constraints(self) -> None:
        self.queries.append(("ENSURE_CONSTRAINTS", None))

    def execute_write(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        if self.responses:
            return self.responses.pop(0)
        return []

    def execute_read(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        return list(self._read_response)

    def execute_read_unvalidated(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        return list(self._read_response)

    def transaction(self):
        from contextlib import nullcontext
        return nullcontext(self)

    serialized_writes = transaction

    def stage_artifact(self, path, payload):
        from processing.run_artifacts import atomic_write_json
        atomic_write_json(path, payload)

    def read_staged_artifact(self, path):
        return None


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

    process_write_action = writer.write_payload(client, payload)

    queries = [query for query, _ in client.queries]
    assert any("DELETE r" in query for query in queries)
    assert not any("MERGE (a)-[r:SERVES]->(p)" in query for query in queries)
    assert process_write_action == "inserted"


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

    process_write_action = writer.write_payload(client, payload)

    dient_writes = [
        parameters
        for query, parameters in client.queries
        if "MERGE (a)-[r:SERVES]->(p)" in query
    ]
    written_cmdb_ids = {entry["cmdb_id"] for entry in dient_writes}

    assert written_cmdb_ids == {"cmdb-1", "cmdb-3"}
    assert process_write_action == "inserted"


def test_graph_writer_marks_follow_up_processes_as_placeholders() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Current Process",
            process_id="proc-1",
            org_unit="",
            roles=[],
            org_units=[],
            org_unit_candidates=[],
            follows_after=["Previous Process"],
            raw_applications=[],
            applications=[],
            source_path="Input/process.txt",
        ),
        matches=[],
    )

    process_write_action = writer.write_payload(client, payload)

    placeholder_queries = [
        query
        for query, _ in client.queries
        if "ON CREATE SET previous.placeholder = true" in query
    ]
    assert len(placeholder_queries) == 1
    assert process_write_action == "inserted"


def test_graph_writer_reuses_single_matching_placeholder_for_real_process() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    client.responses = [
        [{"element_id": "placeholder-1"}],
        [],
    ]
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Current Process",
            process_id="proc-1",
            org_unit="",
            roles=[],
            org_units=[],
            org_unit_candidates=[],
            follows_after=[],
            raw_applications=[],
            applications=[],
            source_path="Input/process.txt",
        ),
        matches=[],
    )

    process_write_action = writer.write_payload(client, payload)

    reuse_queries = [
        query
        for query, _ in client.queries
        if "WHERE elementId(p) = $element_id" in query
    ]
    assert len(reuse_queries) == 1
    assert process_write_action == "updated"


def test_graph_writer_can_cleanup_process_placeholders() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.cleanup_process_placeholders(client)

    cleanup_queries = [
        query
        for query, _ in client.queries
        if "MATCH (p:Process {placeholder: true})" in query and "DETACH DELETE p" in query
    ]
    assert len(cleanup_queries) == 1


def test_graph_writer_writes_role_nodes_with_beteiligt_an_relationship() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Incident Management",
            process_id="proc-1",
            org_unit="Support",
            roles=["1st Level Support", "2nd Level Support"],
            org_units=[],
            org_unit_candidates=[],
            follows_after=[],
            raw_applications=[],
            applications=[],
            source_path="Input/process.bpmn",
        ),
        matches=[],
    )

    process_write_action = writer.write_payload(client, payload)

    queries = [query for query, _ in client.queries]
    assert any("MERGE (r:Role" in query for query in queries)
    assert any("MERGE (r)-[:PARTICIPATES_IN]->(p)" in query for query in queries)
    role_params = [params for query, params in client.queries if "MERGE (r:Role" in query]
    written_roles = {p["role_name"] for p in role_params if p}
    assert written_roles == {"1st Level Support", "2nd Level Support"}
    assert process_write_action == "inserted"


def test_graph_writer_does_not_write_verantwortet_for_process_extraction() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Cross-Team Process",
            process_id="proc-x",
            org_unit="",
            roles=["Team A", "Team B"],
            org_units=[],
            org_unit_candidates=[],
            follows_after=[],
            raw_applications=[],
            applications=[],
            source_path="Input/process.txt",
        ),
        matches=[],
    )

    writer.write_payload(client, payload)

    verantwortet_to_process = [
        query for query, _ in client.queries
        if "RESPONSIBLE_FOR" in query and "Process" in query
    ]
    assert verantwortet_to_process == []


def test_graph_writer_write_role_assignment_creates_kann_einnehmen() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.write_role_assignment(client, "Einkauf", "Einkäufer")

    kann_einnehmen_queries = [
        (query, params) for query, params in client.queries
        if "CAN_ASSUME" in query
    ]
    assert len(kann_einnehmen_queries) == 1
    _, params = kann_einnehmen_queries[0]
    assert params["org_unit_name"] == "Einkauf"
    assert params["role_name"] == "Einkäufer"


def test_graph_writer_write_role_assignment_merges_org_unit_and_role_nodes() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.write_role_assignment(client, "Sales Team", "Sales Team")

    queries = [query for query, _ in client.queries]
    assert any("MERGE (o:OrgUnit" in query for query in queries)
    assert any("MERGE (r:Role" in query for query in queries)


def test_graph_writer_updates_existing_process_node_without_creating_new_one() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    client.responses = [
        [],
        [{"element_id": "existing-1"}],
    ]
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Existing Process",
            process_id="proc-existing",
            org_unit="",
            roles=[],
            org_units=[],
            org_unit_candidates=[],
            follows_after=[],
            raw_applications=[],
            applications=[],
            source_path="Input/process.bpmn",
        ),
        matches=[],
    )

    process_write_action = writer.write_payload(client, payload)

    update_queries = [
        query for query, _ in client.queries if "SET p.name = $process_name" in query and "p.placeholder = false" in query
    ]
    merge_queries = [
        query for query, _ in client.queries if "MERGE (p:Process {process_id: $process_id})" in query
    ]
    assert len(update_queries) >= 1
    assert len(merge_queries) == 0
    assert process_write_action == "updated"


def test_graph_writer_syncs_cmdb_process_entity_as_prozess_node() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.sync_cmdb(
        client,
        NormalizedCmdb(
            entities=[
                CmdbEntity(entity_id="proc-cmdb-1", name="Order Management", entity_type="process"),
            ],
            relations=[],
        ),
    )

    queries = [query for query, _ in client.queries]
    assert any("MERGE (p:Process {process_id: $entity_id})" in query for query in queries)


def test_graph_writer_writes_weak_match_as_koennte_dienen() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Incident Management",
            process_id="proc-1",
            org_unit="",
            roles=[],
            org_units=[],
            org_unit_candidates=[],
            follows_after=[],
            raw_applications=[ApplicationReference(name="Mail", confidence="schwach")],
            applications=[ApplicationReference(name="Mail", confidence="schwach")],
            source_path="Input/process.xml",
        ),
        matches=[
            MatchResult(
                application_name="Mail",
                cmdb_id="cmdb-2",
                matched_name="Mail System",
                confidence="schwach",
                source="fuzzy",
                score=0.72,
            ),
        ],
    )

    writer.write_payload(client, payload)

    koennte_dienen_writes = [
        params for query, params in client.queries if "MAY_SERVE" in query and "SET r.score" in query
    ]
    dient_writes = [
        params for query, params in client.queries if "MERGE (a)-[r:SERVES]->(p)" in query
    ]
    assert len(koennte_dienen_writes) == 1
    assert koennte_dienen_writes[0]["cmdb_id"] == "cmdb-2"
    assert koennte_dienen_writes[0]["score"] == 0.72
    assert len(dient_writes) == 0


def test_graph_writer_deletes_koennte_dienen_on_reimport() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Incident Management",
            process_id="proc-1",
            org_unit="",
            roles=[],
            org_units=[],
            org_unit_candidates=[],
            follows_after=[],
            raw_applications=[],
            applications=[],
            source_path="Input/process.xml",
        ),
        matches=[],
    )

    writer.write_payload(client, payload)

    cleanup_queries = [
        query for query, _ in client.queries if "MAY_SERVE" in query and "DELETE r" in query
    ]
    assert len(cleanup_queries) == 1


def test_graph_writer_dient_carries_raw_name_and_source() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    payload = GraphWritePayload(
        process=ExtractedProcess(
            process_name="Incident Management",
            process_id="proc-1",
            org_unit="",
            roles=[],
            org_units=[],
            org_unit_candidates=[],
            follows_after=[],
            raw_applications=[ApplicationReference(name="Ticket", confidence="stark")],
            applications=[ApplicationReference(name="Ticket", confidence="stark")],
            source_path="Input/process.xml",
        ),
        matches=[
            MatchResult(
                application_name="Ticket",
                cmdb_id="cmdb-1",
                matched_name="Trouble Ticket System",
                confidence="stark",
                source="fuzzy",
                score=0.95,
            ),
        ],
    )

    writer.write_payload(client, payload)

    dient_params = [
        params for query, params in client.queries if "MERGE (a)-[r:SERVES]->(p)" in query
    ]
    assert len(dient_params) == 1
    assert dient_params[0]["raw_name"] == "Ticket"
    assert dient_params[0]["source"] == "strong"


def test_graph_writer_promote_candidate_link_deletes_koennte_dienen_and_writes_dient() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.promote_candidate_link(client, cmdb_id="cmdb-2", process_id="proc-1", raw_name="Mail", matched_name="Mail System")

    delete_queries = [query for query, _ in client.queries if "MAY_SERVE" in query and "DELETE r" in query]
    dient_queries = [query for query, _ in client.queries if "MERGE (a)-[r:SERVES]->(p)" in query]
    assert len(delete_queries) == 1
    assert len(dient_queries) == 1
    dient_params = [params for query, params in client.queries if "MERGE (a)-[r:SERVES]->(p)" in query]
    assert dient_params[0]["raw_name"] == "Mail"
    assert dient_params[0]["source"] == "manuell_bestaetigt"


def test_promote_candidate_link_writes_alias_when_raw_name_differs() -> None:
    """Confirming a weak candidate with a different raw_name creates a confirmed_match Alias node."""
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.promote_candidate_link(client, cmdb_id="cmdb-1", process_id="proc-1", raw_name="SAP CRM", matched_name="SAP SRM")

    alias_queries = [query for query, params in client.queries if "Alias" in query and "MAY_REFER_TO" in query]
    assert len(alias_queries) == 1
    alias_params = [params for query, params in client.queries if "Alias" in query and "MAY_REFER_TO" in query][0]
    assert alias_params["alias_name"] == "SAP CRM"
    assert alias_params["normalized_name"] == "sap crm"
    assert alias_params["source_kind"] == "confirmed_match"


def test_promote_candidate_link_skips_alias_when_names_identical() -> None:
    """No Alias node is written when raw_name and matched_name are the same."""
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.promote_candidate_link(client, cmdb_id="cmdb-1", process_id="proc-1", raw_name="SAP SRM", matched_name="SAP SRM")

    alias_queries = [query for query, _ in client.queries if "Alias" in query and "MAY_REFER_TO" in query]
    assert alias_queries == []


def test_promote_candidate_link_skips_alias_when_names_differ_only_in_case() -> None:
    """No Alias node is written when names differ only in casing (normalize to same value)."""
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.promote_candidate_link(client, cmdb_id="cmdb-1", process_id="proc-1", raw_name="SAP SRM", matched_name="sap srm")

    alias_queries = [query for query, _ in client.queries if "Alias" in query and "MAY_REFER_TO" in query]
    assert alias_queries == []


def test_graph_writer_reject_candidate_link_creates_ablehnung_node() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.reject_candidate_link(
        client,
        cmdb_id="cmdb-2",
        process_id="proc-1",
        prozess_name="Incident Management",
        anwendung_name="Mail",
    )

    ablehnung_queries = [query for query, _ in client.queries if "MERGE (ab:Rejection" in query]
    delete_queries = [query for query, _ in client.queries if "MAY_SERVE" in query and "DELETE r" in query]
    assert len(ablehnung_queries) == 1
    assert len(delete_queries) == 1
    params = [params for query, params in client.queries if "MERGE (ab:Rejection" in query][0]
    assert params["prozess_name"] == "Incident Management"
    assert params["anwendung_name"] == "Mail"


def test_graph_writer_reject_candidate_link_without_cmdb_id_still_creates_ablehnung() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.reject_candidate_link(
        client,
        cmdb_id=None,
        process_id="proc-1",
        prozess_name="Incident Management",
        anwendung_name="Unbekanntes System",
    )

    ablehnung_queries = [query for query, _ in client.queries if "MERGE (ab:Rejection" in query]
    delete_queries = [query for query, _ in client.queries if "MAY_SERVE" in query and "DELETE r" in query]
    assert len(ablehnung_queries) == 1
    assert len(delete_queries) == 0


def test_graph_writer_syncs_cmdb_entities_relations_and_owners() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()

    writer.sync_cmdb(
        client,
        NormalizedCmdb(
            entities=[
                CmdbEntity(entity_id="app-1", name="Seller Service", entity_type="application", owner_name="Team Commerce IT"),
                CmdbEntity(entity_id="if-1", name="Seller Service API", entity_type="interface"),
                CmdbEntity(entity_id="srv-1", name="vm-app-01", entity_type="server", server_type="virtual"),
            ],
            relations=[
                CmdbRelation(source_id="app-1", relation_type="USES_INTERFACE", target_id="if-1"),
                CmdbRelation(source_id="if-1", relation_type="RUNS_ON", target_id="srv-1"),
            ],
        ),
        owner_assignments={"app-1": "Team Commerce IT"},
    )

    queries = [query for query, _ in client.queries]
    assert any("MERGE (a:Application {cmdb_id: $entity_id})" in query for query in queries)
    assert any("MERGE (i:Interface {id: $entity_id})" in query for query in queries)
    assert any("MERGE (s:Server {id: $entity_id})" in query for query in queries)
    assert any("MERGE (source)-[:USES_INTERFACE]->(target)" in query for query in queries)
    assert any("MERGE (source)-[:RUNS_ON]->(target)" in query for query in queries)
    assert any("MERGE (o)-[:RESPONSIBLE_FOR]->(target)" in query for query in queries)


# --- OrgUnit deduplication via canonical name resolution ---

def test_resolve_org_unit_canonical_name_returns_existing_name() -> None:
    """When a matching OrgUnit already exists in DB, its stored name is returned."""
    writer = GraphWriter()
    client = RecordingNeo4jClient(read_response=[{"name": "Sales"}])
    result = writer._resolve_org_unit_canonical_name(client, "SALES")
    assert result == "Sales"


def test_resolve_org_unit_canonical_name_falls_back_to_stripped_input() -> None:
    """When no matching OrgUnit exists, the stripped input name is returned."""
    writer = GraphWriter()
    client = RecordingNeo4jClient(read_response=[])
    result = writer._resolve_org_unit_canonical_name(client, "  Sales  ")
    assert result == "Sales"


def test_write_role_assignment_uses_canonical_name_from_db() -> None:
    """write_role_assignment must use DB-canonical name to prevent case-variant duplicates."""
    writer = GraphWriter()
    client = RecordingNeo4jClient(read_response=[{"name": "Sales"}])
    writer.write_role_assignment(client, "SALES", "Sachbearbeiter")
    merge_params = [params for query, params in client.queries if "MERGE (o:OrgUnit" in query]
    assert len(merge_params) == 1
    assert merge_params[0]["org_unit_name"] == "Sales"


def test_sync_cmdb_uses_canonical_org_unit_name() -> None:
    """sync_cmdb must resolve canonical OrgUnit name before writing RESPONSIBLE_FOR."""
    writer = GraphWriter()
    client = RecordingNeo4jClient(read_response=[{"name": "Vertrieb"}])
    writer.sync_cmdb(
        client,
        NormalizedCmdb(entities=[], relations=[]),
        owner_assignments={"app-1": "VERTRIEB"},
    )
    org_unit_params = [
        params for query, params in client.queries
        if params and "org_unit_name" in params
    ]
    assert len(org_unit_params) == 2  # DELETE MAY_BE_RESPONSIBLE_FOR + MERGE RESPONSIBLE_FOR
    assert all(p["org_unit_name"] == "Vertrieb" for p in org_unit_params)


def test_upsert_org_unit_candidate_creates_open_candidate_with_provenance() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    writer.upsert_org_unit_candidate(
        client,
        candidate_name="  Team Einkauf  ",
        source_path="Input/process.txt",
        process_name="Bestellung anlegen",
        role_name="Einkäufer",
    )
    merge_params = [params for query, params in client.queries if "MERGE (k:OrgCandidate" in query]
    assert len(merge_params) == 1
    assert merge_params[0]["normalized_name"] == "team einkauf"
    assert merge_params[0]["candidate_name"] == "Team Einkauf"
    assert merge_params[0]["source_path"] == "Input/process.txt"
    assert merge_params[0]["process_name"] == "Bestellung anlegen"
    assert merge_params[0]["role_name"] == "Einkäufer"


def test_upsert_org_unit_candidate_skips_blank_names() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    writer.upsert_org_unit_candidate(client, candidate_name="   ")
    assert client.queries == []


def test_load_org_unit_candidates_uses_unvalidated_read_path() -> None:
    """OrgCandidate is excluded from graph_schema.py, so execute_read would reject this query."""
    class ReadPathClient(RecordingNeo4jClient):
        def execute_read(self, query: str, parameters=None):
            raise AssertionError("validated read path must not be used for OrgCandidate lookup")

    client = ReadPathClient(read_response=[
        {
            "candidate_name": "Team Einkauf",
            "normalized_name": "team einkauf",
            "status": "open",
            "mapped_org_unit": "",
            "source_paths": ["Input/process.txt"],
            "process_names": ["Bestellung anlegen"],
            "role_names": [],
            "first_seen": "2026-08-01",
            "last_seen": "2026-08-01",
        }
    ])
    writer = GraphWriter()

    result = writer.load_org_unit_candidates(client, status="open")

    assert result[0]["candidate_name"] == "Team Einkauf"
    assert client.queries[0][1] == {"status": "open"}


def test_map_org_unit_candidate_sets_status_and_target() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    writer.map_org_unit_candidate(client, "Team Einkauf", "Einkauf")
    set_params = [params for query, params in client.queries if "k.status = 'mapped'" in query]
    assert len(set_params) == 1
    assert set_params[0]["normalized_name"] == "team einkauf"
    assert set_params[0]["target_org_unit"] == "Einkauf"


def test_reject_org_unit_candidate_sets_status_rejected() -> None:
    writer = GraphWriter()
    client = RecordingNeo4jClient()
    writer.reject_org_unit_candidate(client, "Team Einkauf")
    set_params = [params for query, params in client.queries if "k.status = 'rejected'" in query]
    assert len(set_params) == 1
    assert set_params[0]["normalized_name"] == "team einkauf"
