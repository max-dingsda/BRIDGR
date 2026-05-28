from __future__ import annotations


QUERY_NODE_SCHEMA: dict[str, tuple[str, ...]] = {
    "Prozess": ("prozess_id", "name"),
    "Anwendung": ("id", "cmdb_id", "name"),
    "Schnittstelle": ("id", "name"),
    "Server": ("id", "name", "server_type"),
    "OrgEinheit": ("name",),
}

QUERY_RELATIONSHIP_SCHEMA: dict[str, tuple[str, ...]] = {
    "DIENT": ("konfidenz",),
    "VERANTWORTET": (),
    "FOLGT_AUF": (),
}


def build_query_schema_reference() -> str:
    node_lines = [
        f"- `{label}`: {', '.join(properties)}"
        for label, properties in QUERY_NODE_SCHEMA.items()
    ]
    relationship_lines = [
        f"- `[:{relationship}]`: {', '.join(properties) if properties else 'no properties'}"
        for relationship, properties in QUERY_RELATIONSHIP_SCHEMA.items()
    ]
    return (
        "Use only the following graph schema.\n\n"
        "Node labels and properties:\n"
        + "\n".join(node_lines)
        + "\n\nRelationship types and properties:\n"
        + "\n".join(relationship_lines)
    )
