from dataclasses import replace
from pathlib import Path
import re

import pytest

from core.org_resolution import resolve_organization
from services import merge_state
from services.archimate_export_service import _read_nodes
from services.snapshot_service import create_snapshot, restore_snapshot
from skills.graph_writer import GraphWriter


def test_every_prompt_example_is_executable_through_chat_boundary(chat_client):
    prompt = (Path(__file__).resolve().parents[2] / "prompts/chat_system.md").read_text(encoding="utf-8")
    examples = re.findall(r"```cypher\s*\n(.*?)```", prompt, re.S)
    assert len(examples) >= 17
    for query in examples:
        chat_client.execute_read(query.strip())


def test_ambiguous_alias_is_not_selected_by_database_row_order(graph_client):
    graph_client.execute_write("""
        CREATE (a:Alias {normalized_name:'ops'}), (x:OrgUnit {name:'Operations West'}),
               (y:OrgUnit {name:'Operations East'})
        CREATE (a)-[:MAY_REFER_TO]->(x), (a)-[:MAY_REFER_TO]->(y)
    """)
    writer = GraphWriter()
    aliases = writer.load_org_unit_aliases_from_neo4j(graph_client)
    result = resolve_organization("ops", writer.load_org_units_from_neo4j(graph_client), aliases)
    assert result.status == "ambiguous" and result.name == ""
    assert len(result.candidates) == 2


def test_merge_preserves_native_property_types_and_reserved_property_names(graph_client):
    from neo4j.time import DateTime, Duration
    from neo4j.spatial import WGS84Point
    props = {"when": DateTime(2026, 9, 7, 12, 0, 0), "duration": Duration(months=1, seconds=2),
             "location": WGS84Point((13.4, 52.5)), "bytes": bytearray(b"BRIDGR")}
    with graph_client.transaction():
        rows = graph_client.execute_write("""
            CREATE (s:OrgUnit {name:'Source'}), (t:OrgUnit {name:'Target'}), (p:Process {process_id:'p1'})
            CREATE (s)-[r:RESPONSIBLE_FOR]->(p) SET r=$props
            SET s.type='Date', s.value='plain business value'
            RETURN elementId(s) AS source, elementId(t) AS target
        """, {"props": props})
        payload = merge_state.merge(graph_client, "OrgUnit", rows[0]["source"], rows[0]["target"])
    # JSON round trip models storage in ManualDecision.payload_json.
    import json
    with graph_client.transaction():
        merge_state.undo(graph_client, json.loads(json.dumps(payload)))
    restored = graph_client.execute_read_unvalidated("""
        MATCH (s:OrgUnit {name:'Source'})-[r:RESPONSIBLE_FOR]->(:Process)
        RETURN properties(r) AS props, s.type AS type, s.value AS value
    """)
    assert restored == [{"props": props, "type": "Date", "value": "plain business value"}]
    assert {node["label"] for node in _read_nodes(graph_client)} == {"OrgUnit"}


def test_old_merge_payload_is_rejected_before_accessing_database():
    with pytest.raises(ValueError, match="Historischer Merge"):
        merge_state.undo(None, {"entity_type": "OrgUnit", "relationships": []})


@pytest.mark.parametrize("payload", [{"version": 2}, {"version": 2, "focus": [], "before": {}, "after": {}}])
def test_malformed_versioned_merge_payload_is_rejected_before_writes(payload):
    with pytest.raises(ValueError, match="Merge-Payload"):
        merge_state.undo(None, payload)


def test_merge_id_constraint_rejects_duplicate_identity(graph_client):
    from core.neo4j_utils import Neo4jQueryError
    graph_client.execute_write("CREATE (:OrgUnit:__BridgrIdentity {name:'One', __bridgr_id:'duplicate'})")
    with pytest.raises(Neo4jQueryError):
        graph_client.execute_write("CREATE (:Process:__BridgrIdentity {process_id:'two', __bridgr_id:'duplicate'})")


@pytest.mark.parametrize("with_node", [False, True])
def test_restore_validates_graph_without_relationships(graph_client, isolated_neo4j_config, tmp_path, with_node):
    config = replace(isolated_neo4j_config, output_path=str(tmp_path))
    if with_node:
        graph_client.execute_write("CREATE (:Process {process_id:'only', name:'Only'})")
    snapshot = create_snapshot(config, graph_client, trigger="test", operation="zero-edges")
    graph_client.execute_write("CREATE (:OrgUnit {name:'Later'})")
    restored = restore_snapshot(config, graph_client, snapshot.snapshot_id)
    assert restored.node_count == int(with_node) and restored.relationship_count == 0
