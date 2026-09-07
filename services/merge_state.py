"""Versioned local graph before/after states for lossless, conflict-checked merge undo."""
import base64
import json
from uuid import uuid4

from core.graph_schema import QUERY_RELATIONSHIP_SCHEMA
from services.alias_service import normalize_alias_name, write_merged_org_unit_alias, write_merged_process_alias


IDENTITY = "__bridgr_id"
VERSION = 2


def encode(value):
    from neo4j.time import Date, DateTime, Duration, Time
    from neo4j.spatial import Point
    if isinstance(value, (Date, DateTime, Time)):
        return {"type": type(value).__name__, "value": value.iso_format()}
    if isinstance(value, Duration):
        return {"type": "Duration", "value": list(value)}
    if isinstance(value, Point):
        return {"type": "Point", "srid": value.srid, "value": list(value)}
    if isinstance(value, (bytes, bytearray)):
        return {"type": "Bytes", "value": base64.b64encode(value).decode("ascii")}
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    return value


def decode(value):
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    from neo4j.time import Date, DateTime, Duration, Time
    from neo4j.spatial import CartesianPoint, WGS84Point
    kind = value.get("type")
    if kind in {"Date", "DateTime", "Time"} and set(value) == {"type", "value"}:
        return {"Date": Date, "DateTime": DateTime, "Time": Time}[kind].from_iso_format(value["value"])
    if kind == "Duration" and set(value) == {"type", "value"}:
        months, days, seconds, nanoseconds = value["value"]
        return Duration(months=months, days=days, seconds=seconds, nanoseconds=nanoseconds)
    if kind == "Bytes" and set(value) == {"type", "value"}:
        return bytearray(base64.b64decode(value["value"]))
    if kind == "Point" and set(value) == {"type", "value", "srid"}:
        point = WGS84Point if value["srid"] in {4326, 4979} else CartesianPoint
        return point(value["value"])
    return {key: decode(item) for key, item in value.items()}


def _decode_properties(properties):
    return {key: decode(value) for key, value in properties.items()}


def _identifier(value):
    return "`" + value.replace("`", "``") + "`"


def _ensure_identity(client, element_id):
    rows = client.execute_write(
        "MATCH (n) WHERE elementId(n)=$element_id "
        "SET n:__BridgrIdentity, n.__bridgr_id=coalesce(n.__bridgr_id,$identity) RETURN n.__bridgr_id AS identity",
        {"element_id": element_id, "identity": uuid4().hex},
    )
    if len(rows) != 1:
        raise ValueError("Merge-Objekt wurde nicht eindeutig gefunden.")
    return rows[0]["identity"]


def capture(client, identities):
    nodes = client.execute_read_unvalidated(
        "MATCH (n:__BridgrIdentity) WHERE n.__bridgr_id IN $ids "
        "RETURN n.__bridgr_id AS identity, labels(n) AS labels, properties(n) AS properties",
        {"ids": identities},
    )
    edges = client.execute_read_unvalidated(
        "MATCH (n:__BridgrIdentity) WHERE n.__bridgr_id IN $ids MATCH (n)-[edge]-() "
        "WITH DISTINCT edge AS r, startNode(edge) AS s, endNode(edge) AS t "
        "RETURN elementId(s) AS source_element, elementId(t) AS target_element, "
        "s.__bridgr_id AS source, t.__bridgr_id AS target, type(r) AS type, properties(r) AS properties",
        {"ids": identities},
    )
    relationships = []
    for edge in edges:
        for endpoint in ("source", "target"):
            if not edge[endpoint]:
                edge[endpoint] = _ensure_identity(client, edge[endpoint + "_element"])
        relationships.append({key: encode(edge[key]) for key in ("source", "target", "type", "properties")})
    for node in nodes:
        node["labels"] = sorted(node["labels"])
    return {"nodes": sorted(encode(nodes), key=lambda row: row["identity"]),
            "relationships": sorted(relationships, key=lambda row: json.dumps(row, sort_keys=True))}


def _strength(properties):
    source = properties.get("source", "")
    if source in {"manueller_link", "manuell_bestaetigt"}: return 3
    if properties.get("confidence") in {"stark", "strong"}: return 2
    return 1


def merge_properties(existing, incoming):
    result = {**incoming, **existing}
    if _strength(incoming) > _strength(existing):
        result.update(incoming)
        # Identity/provenance identifiers already on the target must not be replaced.
        result.update({key: value for key, value in existing.items() if key.endswith("_id") or key.startswith("archimate_")})
    return result


def _write_relationship(client, edge):
    query = ("MATCH (s:__BridgrIdentity {__bridgr_id:$source}), (t:__BridgrIdentity {__bridgr_id:$target}) "
             f"CREATE (s)-[r:{_identifier(edge['type'])}]->(t) SET r=$properties")
    client.execute_write(query, {**edge, "properties": _decode_properties(edge["properties"])})


def merge(client, label, source_element, target_element):
    """Called within the merge transaction after a validated snapshot."""
    if label not in {"OrgUnit", "Process"} or source_element == target_element:
        raise ValueError("Ungültige Merge-Auswahl.")
    source_id = _ensure_identity(client, source_element)
    target_id = _ensure_identity(client, target_element)
    rows = client.execute_read_unvalidated(
        f"MATCH (s:{label} {{__bridgr_id:$source}}), (t:{label} {{__bridgr_id:$target}}) "
        "RETURN s.name AS source_name, t.name AS target_name", {"source": source_id, "target": target_id})
    if len(rows) != 1:
        raise ValueError("Quelle oder Ziel fehlt oder ist nicht eindeutig.")
    source_name = rows[0]["source_name"]
    alias_name = normalize_alias_name(source_name)
    aliases = client.execute_read_unvalidated(
        "MATCH (a:Alias {normalized_name:$name}) RETURN elementId(a) AS element_id", {"name": alias_name})
    focus = [source_id, target_id] + [_ensure_identity(client, row["element_id"]) for row in aliases]
    before = capture(client, focus)
    source = next(row for row in before["nodes"] if row["identity"] == source_id)
    target = next(row for row in before["nodes"] if row["identity"] == target_id)
    source_edges = [edge for edge in before["relationships"] if source_id in (edge["source"], edge["target"])]
    if any(edge["type"] not in QUERY_RELATIONSHIP_SCHEMA for edge in source_edges):
        raise ValueError("Merge enthält nicht unterstützte Beziehungen; keine Daten wurden verworfen.")
    # Replace only incident source/target edges; all original properties are retained in before.
    transferred = {}
    for edge in sorted(before["relationships"], key=lambda edge: source_id in (edge["source"], edge["target"])):
        if source_id not in (edge["source"], edge["target"]) and target_id not in (edge["source"], edge["target"]):
            continue
        moved = {**edge, "source": target_id if edge["source"] == source_id else edge["source"],
                 "target": target_id if edge["target"] == source_id else edge["target"]}
        key = (moved["source"], moved["target"], moved["type"])
        if key in transferred:
            moved["properties"] = merge_properties(transferred[key]["properties"], moved["properties"])
        transferred[key] = moved
    client.execute_write("MATCH (n:__BridgrIdentity) WHERE n.__bridgr_id IN $ids MATCH (n)-[r]-() WITH DISTINCT r DELETE r",
                         {"ids": [source_id, target_id]})
    client.execute_write("MATCH (source:__BridgrIdentity {__bridgr_id:$id}) DETACH DELETE source", {"id": source_id})
    props = {**_decode_properties(source["properties"]), **_decode_properties(target["properties"]), IDENTITY: target_id}
    client.execute_write("MATCH (target:__BridgrIdentity {__bridgr_id:$id}) SET target=$props", {"id": target_id, "props": props})
    for edge in transferred.values():
        _write_relationship(client, edge)
    if label == "OrgUnit":
        write_merged_org_unit_alias(client, source_name, rows[0]["target_name"])
    else:
        write_merged_process_alias(client, source_name, target_element_id=target_element)
    aliases = client.execute_read_unvalidated(
        "MATCH (a:Alias {normalized_name:$name}) RETURN elementId(a) AS element_id", {"name": alias_name})
    focus = sorted(set(focus + [_ensure_identity(client, row["element_id"]) for row in aliases]))
    # Do not query the just-deleted source through its transaction-local index entry.
    # Keep its identity in the payload focus so a later resurrection conflicts with undo.
    after = capture(client, [identity for identity in focus if identity != source_id])
    return {"version": VERSION, "entity_type": label, "source_name": source_name,
            "target_name": rows[0]["target_name"], "focus": focus, "before": before, "after": after}


def undo(client, payload):
    if payload.get("version") != VERSION:
        raise ValueError("Historischer Merge enthält keinen vollständigen Vorzustand; sichere Rücknahme ist nicht möglich.")
    _validate_undo_payload(payload)
    focus = payload["focus"]
    before, after = payload["before"], payload["after"]
    if capture(client, focus) != after:
        raise ValueError("Merge wurde zwischenzeitlich verändert; Rücknahme wegen Konflikt abgebrochen.")
    before_ids = {node["identity"] for node in before["nodes"]}
    endpoints = {edge[key] for edge in before["relationships"] for key in ("source", "target")} - before_ids
    rows = client.execute_read_unvalidated("MATCH (n:__BridgrIdentity) WHERE n.__bridgr_id IN $ids RETURN n.__bridgr_id AS identity", {"ids": sorted(endpoints)})
    if {row["identity"] for row in rows} != endpoints:
        raise ValueError("Beziehungsziel fehlt; Rücknahme wegen Konflikt abgebrochen.")
    client.execute_write("MATCH (n:__BridgrIdentity) WHERE n.__bridgr_id IN $ids MATCH (n)-[r]-() WITH DISTINCT r DELETE r", {"ids": focus})
    # Delete affected nodes before recreating them so transferred unique IDs cannot collide.
    client.execute_write("MATCH (n:__BridgrIdentity) WHERE n.__bridgr_id IN $ids DETACH DELETE n", {"ids": focus})
    for node in before["nodes"]:
        labels = ":".join(_identifier(label) for label in node["labels"])
        client.execute_write(f"CREATE (n:{labels}) SET n=$props", {"props": _decode_properties(node["properties"])})
    for edge in before["relationships"]:
        _write_relationship(client, edge)


def _validate_undo_payload(payload):
    try:
        focus = payload["focus"]
        if not isinstance(focus, list) or not focus or any(not isinstance(value, str) or not value for value in focus):
            raise ValueError
        if len(set(focus)) != len(focus):
            raise ValueError
        for state in (payload["before"], payload["after"]):
            if not isinstance(state["nodes"], list) or not isinstance(state["relationships"], list):
                raise ValueError
            identities = set()
            for node in state["nodes"]:
                identity = node["identity"]
                if identity not in focus or identity in identities or node["properties"].get(IDENTITY) != identity:
                    raise ValueError
                identities.add(identity)
                if not isinstance(node["labels"], list) or not node["labels"] or any(not isinstance(label, str) or not label for label in node["labels"]):
                    raise ValueError
            for edge in state["relationships"]:
                if any(not isinstance(edge[key], str) or not edge[key] for key in ("source", "target", "type")):
                    raise ValueError
                if not isinstance(edge["properties"], dict) or not ({edge["source"], edge["target"]} & set(focus)):
                    raise ValueError
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError("Merge-Payload ist unvollständig oder ungültig; sichere Rücknahme ist nicht möglich.") from exc
