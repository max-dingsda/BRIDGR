from dataclasses import replace
import json

import pytest

from services import merge_service, correction_service
from services.decision_service import list_recent_manual_decisions


def domain_state(client):
    rows = client.execute_read_unvalidated("""
        MATCH (n) WHERE NOT n:ManualDecision AND NOT n:__BridgrWriteLock AND NOT n:__BridgrArtifact
        RETURN labels(n) AS labels, properties(n) AS props
    """)
    for row in rows:
        row["props"].pop("__bridgr_id", None)
        row["labels"] = [label for label in row["labels"] if label != "__BridgrIdentity"]
        row["labels"].sort()
    edges = client.execute_read_unvalidated("""
        MATCH (s)-[r]->(t)
        RETURN s.name AS source, t.name AS target, type(r) AS type, properties(r) AS props
    """)
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True)), sorted(edges, key=lambda r: json.dumps(r, sort_keys=True))


@pytest.mark.parametrize("label", ["OrgUnit", "Process"])
def test_merge_undo_restores_all_properties(graph_client, isolated_neo4j_config, tmp_path, monkeypatch, label):
    config = replace(isolated_neo4j_config, output_path=str(tmp_path))
    monkeypatch.setattr(merge_service, "get_session_neo4j_client", lambda _: graph_client)
    monkeypatch.setattr(correction_service, "get_session_neo4j_client", lambda _: graph_client)
    if label == "Process":
        graph_client.execute_write("""
            CREATE (s:Process {name:'Source', process_id:'p1', extra:'source'})
            CREATE (t:Process {name:'Target', process_id:'p2', extra:'target'})
            CREATE (a:Application {name:'ERP', cmdb_id:'a1'})
            CREATE (a)-[:SERVES {source:'manuell_bestaetigt', raw_name:'SAP', confidence:'stark', score:0.91}]->(s)
            CREATE (a)-[:SERVES {source:'strong', confidence:'stark', extra:'keep'}]->(t)
            CREATE (s)-[:FOLLOWS {extra:'self'}]->(s)
        """)
        ids = graph_client.execute_read_unvalidated("MATCH (p:Process) RETURN p.name AS name, elementId(p) AS id")
        ids = {row["name"]: row["id"] for row in ids}
        action = lambda: merge_service.merge_processes(config, ids["Source"], ids["Target"])
    else:
        graph_client.execute_write("""
            CREATE (s:OrgUnit {name:'Source', extra:'source'})
            CREATE (t:OrgUnit {name:'Target', extra:'target'})
            CREATE (p:Process {name:'Order', process_id:'p1'})
            CREATE (s)-[:RESPONSIBLE_FOR {source:'manual', extra:'source edge'}]->(p)
            CREATE (t)-[:RESPONSIBLE_FOR {extra:'target edge'}]->(p)
        """)
        action = lambda: merge_service.merge_org_units(config, "Source", "Target")
    before = domain_state(graph_client)
    level, message = action()
    assert level == "success", message
    decision = list_recent_manual_decisions(graph_client)[0]
    level, message = correction_service.revert_manual_decision(config, decision.decision_id)
    assert level == "success", message
    assert domain_state(graph_client) == before
    assert correction_service.revert_manual_decision(config, decision.decision_id)[0] == "warning"


def test_later_target_change_blocks_undo_without_partial_mutation(graph_client, isolated_neo4j_config, tmp_path, monkeypatch):
    config = replace(isolated_neo4j_config, output_path=str(tmp_path))
    monkeypatch.setattr(merge_service, "get_session_neo4j_client", lambda _: graph_client)
    monkeypatch.setattr(correction_service, "get_session_neo4j_client", lambda _: graph_client)
    graph_client.execute_write("CREATE (:OrgUnit {name:'Source'}), (:OrgUnit {name:'Target'})")
    assert merge_service.merge_org_units(config, "Source", "Target")[0] == "success"
    decision = list_recent_manual_decisions(graph_client)[0]
    graph_client.execute_write("MATCH (t:OrgUnit {name:'Target'}) SET t.extra='later change'")
    before = domain_state(graph_client)
    level, message = correction_service.revert_manual_decision(config, decision.decision_id)
    assert level == "error" and "Konflikt" in message
    assert domain_state(graph_client) == before


def test_merge_undo_preserves_shared_alias(graph_client, isolated_neo4j_config, tmp_path, monkeypatch):
    config = replace(isolated_neo4j_config, output_path=str(tmp_path))
    monkeypatch.setattr(merge_service, "get_session_neo4j_client", lambda _: graph_client)
    monkeypatch.setattr(correction_service, "get_session_neo4j_client", lambda _: graph_client)
    graph_client.execute_write("""
        CREATE (:OrgUnit {name:'Source'}), (:OrgUnit {name:'Target'}),
               (a:Alias {name:'Source', normalized_name:'source', extra:'shared'}),
               (p:Process {name:'Elsewhere', process_id:'other'})
        CREATE (a)-[:MAY_REFER_TO {source_kind:'knowledge_base', extra:'retain'}]->(p)
    """)
    before = domain_state(graph_client)
    assert merge_service.merge_org_units(config, "Source", "Target")[0] == "success"
    decision = list_recent_manual_decisions(graph_client)[0]
    assert correction_service.revert_manual_decision(config, decision.decision_id)[0] == "success"
    assert domain_state(graph_client) == before


def test_merge_rolls_back_if_audit_fails(graph_client, isolated_neo4j_config, tmp_path, monkeypatch):
    config = replace(isolated_neo4j_config, output_path=str(tmp_path))
    monkeypatch.setattr(merge_service, "get_session_neo4j_client", lambda _: graph_client)
    def fail(*args):
        raise RuntimeError("injected merge audit failure")
    monkeypatch.setattr(merge_service, "create_manual_decision", fail)
    graph_client.execute_write("CREATE (:OrgUnit {name:'Source'}), (:OrgUnit {name:'Target'})")
    before = domain_state(graph_client)
    with pytest.raises(RuntimeError, match="audit"):
        merge_service.merge_org_units(config, "Source", "Target")
    assert domain_state(graph_client) == before
