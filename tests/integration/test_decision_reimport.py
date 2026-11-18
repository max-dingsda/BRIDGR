from core.app_config import AppConfig
from services.review_service import rerun_single_document_from_artifact
from skills.graph_writer import GraphWriter
from services.review_service import reconstruct_extracted_process, reconstruct_match_result


def document(name="Renamed process", process_id="p1", applications=None):
    return {"extracted_process": {
        "process_name": name, "process_id": process_id,
        "applications": [{"name": n} for n in (applications or [])],
        "source_path": "Input/test.txt",
    }}


def reimport(client, artifact):
    writer = GraphWriter()
    result = rerun_single_document_from_artifact(
        artifact, AppConfig(), [], writer.get_confirmed_links_from_neo4j(client),
        writer.get_rejected_decisions_from_neo4j(client),
    )
    payload = result["graph_payload"]
    writer.write_payload(client, writer.build_payload(
        reconstruct_extracted_process(payload["process"]),
        [reconstruct_match_result(m) for m in payload["matches"]],
    ))
    return result


def test_confirmed_link_survives_rename_and_removed_raw_term(graph_client):
    graph_client.execute_write("""
        CREATE (p:Process {process_id:'p1', name:'Original'})
        CREATE (a:Application {cmdb_id:'a1', name:'ERP'})
        CREATE (a)-[:SERVES {source:'manuell_bestaetigt', raw_name:'SAP', confidence:'stark'}]->(p)
    """)
    for _ in range(2):
        reimport(graph_client, document())
    rows = graph_client.execute_read_unvalidated("""
        MATCH (:Application)-[r:SERVES]->(p:Process {process_id:'p1'})
        RETURN p.name AS name, properties(r) AS props
    """)
    assert rows == [{"name": "Renamed process", "props": {
        "source": "manuell_bestaetigt", "raw_name": "SAP", "confidence": "stark"}}]


def test_reimport_keeps_manual_serves_link_when_no_match_is_rewritten(graph_client):
    """Prevent data loss when a process re-import yields no application matches."""
    graph_client.execute_write("""
        CREATE (p:Process {process_id:'p1', name:'Original'})
        CREATE (a:Application {cmdb_id:'a1', name:'ERP'})
        CREATE (a)-[:SERVES {source:'manueller_link', raw_name:'ERP', confidence:'stark'}]->(p)
    """)

    writer = GraphWriter()
    process = reconstruct_extracted_process(document()["extracted_process"])
    writer.write_payload(graph_client, writer.build_payload(process, []))

    rows = graph_client.execute_read_unvalidated("""
        MATCH (a:Application {cmdb_id:'a1'})-[r:SERVES]->(p:Process {process_id:'p1'})
        RETURN a.name AS application, properties(r) AS props
    """)
    assert rows == [{"application": "ERP", "props": {
        "source": "manueller_link", "raw_name": "ERP", "confidence": "stark"}}]


def test_bpmn_reimport_does_not_delete_archimate_predecessor(graph_client):
    """Prevent a real ArchiMate process from becoming a disposable placeholder."""
    writer = GraphWriter()
    writer.merge_archimate_node(
        graph_client,
        label="Process",
        name="ArchiMate predecessor",
        archimate_id="arch-process-1",
        archimate_source="architecture.archimate",
        archimate_type="BusinessProcess",
    )
    process = reconstruct_extracted_process({
        "process_name": "Current BPMN process",
        "process_id": "bpmn-1",
        "follows_after": ["ArchiMate predecessor"],
        "source_path": "Input/current.bpmn",
    })

    writer.write_payload(graph_client, writer.build_payload(process, []))
    writer.cleanup_process_placeholders(graph_client)

    rows = graph_client.execute_read_unvalidated("""
        MATCH (current:Process {process_id:'bpmn-1'})-[:FOLLOWS]->(previous:Process)
        RETURN previous.archimate_id AS archimate_id, previous.placeholder AS placeholder
    """)
    assert rows == [{"archimate_id": "arch-process-1", "placeholder": False}]


def test_rejection_uses_process_identity_and_survives_rename(graph_client):
    graph_client.execute_write("CREATE (:Process {process_id:'p1', name:'Original'})")
    GraphWriter().reject_candidate_link(graph_client, cmdb_id=None, process_id="p1",
                                       prozess_name="Original", anwendung_name="SAP")
    result = reimport(graph_client, document(applications=["SAP"]))
    assert result["matches"][0]["source"] == "rejected"
    other = reimport(graph_client, document(process_id="p2", applications=["SAP"]))
    assert other["matches"][0]["source"] == "unmatched"


def test_confirmed_link_does_not_cross_same_named_processes(graph_client):
    graph_client.execute_write("""
        CREATE (p:Process {process_id:'p1', name:'Shared'})
        CREATE (:Process {process_id:'p2', name:'Shared'})
        CREATE (a:Application {cmdb_id:'a1', name:'ERP'})
        CREATE (a)-[:SERVES {source:'manueller_link', raw_name:'SAP', confidence:'stark'}]->(p)
    """)
    result = reimport(graph_client, document(name="Shared", process_id="p2", applications=["SAP"]))
    assert result["matches"][0]["source"] == "unmatched"


def test_ambiguous_legacy_rejection_requires_clarification(graph_client):
    import pytest
    graph_client.execute_write("""
        CREATE (:Process {process_id:'p1', name:'Shared'})
        CREATE (:Process {process_id:'p2', name:'Shared'})
        CREATE (:Rejection {prozess_name:'Shared', anwendung_name:'SAP'})
    """)
    with pytest.raises(ValueError, match="(?i)ambiguous|mehrdeutig"):
        GraphWriter().get_rejected_decisions_from_neo4j(graph_client)


def test_unique_legacy_rejection_survives_repeated_rename(graph_client):
    graph_client.execute_write("""
        CREATE (:Process {process_id:'p1', name:'Original'})
        CREATE (:Rejection {prozess_name:'Original', anwendung_name:'SAP'})
    """)
    for name in ("Renamed", "Renamed again"):
        result = reimport(graph_client, document(name=name, applications=["SAP"]))
        assert result["matches"][0]["source"] == "rejected"
