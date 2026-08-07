from __future__ import annotations

from dataclasses import dataclass
import json
import re


# Unicode-aware identifier: starts with letter/underscore, followed by word chars.
# Necessary because BRIDGR relationship types contain umlauts (MAY_SERVE).
_IDENT = r"[^\W\d]\w*"


@dataclass(frozen=True, slots=True)
class RelationshipPattern:
    relationship_type: str
    source_label: str
    target_label: str
    properties: tuple[str, ...] = ()


QUERY_NODE_SCHEMA: dict[str, tuple[str, ...]] = {
    "Process": ("process_id", "name", "archimate_type", "archimate_id"),
    "Application": ("id", "cmdb_id", "name", "archimate_type", "archimate_id"),
    "Interface": ("id", "name", "archimate_type", "archimate_id"),
    "Server": ("id", "name", "server_type", "archimate_type", "archimate_id"),
    "OrgUnit": ("name",),
    "Role": ("name", "archimate_type", "archimate_id", "role_only"),
    "Alias": ("normalized_name", "name", "source_kind"),
    "Capability":    ("name", "archimate_type", "archimate_id"),
    "Resource":     ("name", "archimate_type", "archimate_id"),
    "Goal":          ("name", "archimate_type", "archimate_id"),
    "Requirement":   ("name", "archimate_type", "archimate_id"),
    "Context":       ("name", "archimate_type", "archimate_id"),
    "Stakeholder":   ("name", "archimate_type", "archimate_id"),
    "Risk":        ("name", "archimate_type", "archimate_id"),
    "DataObject":   ("name", "archimate_type", "archimate_id"),
    "Infrastructure": ("name", "archimate_type", "archimate_id"),
}

QUERY_RELATIONSHIP_PATTERNS: tuple[RelationshipPattern, ...] = (
    RelationshipPattern("SERVES", "Application", "Process", ("confidence", "source")),
    RelationshipPattern("PARTICIPATES_IN", "Role", "Process"),
    RelationshipPattern("CAN_ASSUME", "OrgUnit", "Role"),
    RelationshipPattern("RESPONSIBLE_FOR", "OrgUnit", "Process"),
    RelationshipPattern("RESPONSIBLE_FOR", "OrgUnit", "Application"),
    RelationshipPattern("RESPONSIBLE_FOR", "OrgUnit", "Interface"),
    RelationshipPattern("RESPONSIBLE_FOR", "OrgUnit", "Server"),
    RelationshipPattern("RESPONSIBLE_FOR", "OrgUnit", "Infrastructure"),
    RelationshipPattern("FOLLOWS", "Process", "Process"),
    RelationshipPattern("USES_INTERFACE", "Application", "Interface"),
    RelationshipPattern("RUNS_ON", "Application", "Server"),
    RelationshipPattern("RUNS_ON", "Interface", "Server"),
    RelationshipPattern("MAY_SERVE", "Application", "Process", ("score",)),
    RelationshipPattern("MAY_REFER_TO", "Alias", "Application", ("source_kind",)),
    RelationshipPattern("MAY_REFER_TO", "Alias", "OrgUnit", ("source_kind",)),
    RelationshipPattern("AFFECTS", "Risk", "Application"),
    RelationshipPattern("AFFECTS", "Risk", "Process"),
    RelationshipPattern("AFFECTS", "Risk", "Server"),
    RelationshipPattern("AFFECTS", "Risk", "Interface"),
    RelationshipPattern("MITIGATES", "Capability", "Risk"),
    RelationshipPattern("MITIGATES", "Application", "Risk"),
    RelationshipPattern("REALIZES", "Capability", "Process"),
    RelationshipPattern("REALIZES", "Capability", "Application"),
    RelationshipPattern("REALIZES", "Requirement", "Goal"),
    RelationshipPattern("REQUIRES", "Process", "Resource"),
    RelationshipPattern("REQUIRES", "Application", "Resource"),
    RelationshipPattern("SUPPORTS", "Application", "Goal"),
    RelationshipPattern("SUPPORTS", "Process", "Goal"),
    RelationshipPattern("SUPPORTS", "Process", "Capability"),
    RelationshipPattern("SUPPORTS", "Application", "Capability"),
    RelationshipPattern("PROCESSES", "Application", "DataObject"),
    RelationshipPattern("PROCESSES", "Process", "DataObject"),
    RelationshipPattern("RUNS_ON", "Application", "Infrastructure"),
    RelationshipPattern("INFLUENCES", "Context", "Goal"),
    RelationshipPattern("INFLUENCES", "Context", "Requirement"),
    RelationshipPattern("INFLUENCES", "Requirement", "Process"),
    RelationshipPattern("INFLUENCES", "Requirement", "Application"),
    RelationshipPattern("INFLUENCES", "Requirement", "Interface"),
    RelationshipPattern("INFLUENCES", "Requirement", "Server"),
    RelationshipPattern("CONNECTED_TO", "Stakeholder", "Goal"),
    RelationshipPattern("CONNECTED_TO", "Stakeholder", "Requirement"),
    RelationshipPattern("CONNECTED_TO", "Stakeholder", "Process"),
    RelationshipPattern("CONNECTED_TO", "Stakeholder", "Application"),
    RelationshipPattern("CONNECTED_TO", "OrgUnit", "Requirement"),
    RelationshipPattern("CONNECTED_TO", "Stakeholder", "Context"),
    RelationshipPattern("REALIZES", "Capability", "Goal"),
    RelationshipPattern("REALIZES", "Capability", "Requirement"),
    RelationshipPattern("INFLUENCES", "Requirement", "Requirement"),
)

QUERY_RELATIONSHIP_SCHEMA: dict[str, tuple[str, ...]] = {}
for _pattern in QUERY_RELATIONSHIP_PATTERNS:
    QUERY_RELATIONSHIP_SCHEMA.setdefault(_pattern.relationship_type, _pattern.properties)

# CONNECTED_TO is unrestricted — no label-pair validation applied.
_UNRESTRICTED_RELATIONSHIP_TYPES: frozenset[str] = frozenset({"CONNECTED_TO"})


def build_query_schema_reference() -> str:
    node_lines = [
        f"- `{label}`: {', '.join(properties)}"
        for label, properties in QUERY_NODE_SCHEMA.items()
    ]
    relationship_lines = [
        f"- `(:{pattern.source_label})-[:{pattern.relationship_type}]->(:{pattern.target_label})`"
        for pattern in QUERY_RELATIONSHIP_PATTERNS
    ]
    relationship_property_lines = [
        f"- `[:{relationship}]`: {', '.join(properties) if properties else 'no properties'}"
        for relationship, properties in QUERY_RELATIONSHIP_SCHEMA.items()
    ]
    return (
        "Use only the following graph schema.\n\n"
        "Node labels and properties:\n"
        + "\n".join(node_lines)
        + "\n\nAllowed relationship patterns and directions:\n"
        + "\n".join(relationship_lines)
        + "\n\nRelationship types and properties:\n"
        + "\n".join(relationship_property_lines)
        + "\n\nNever invent additional relationship types, labels, directions, or properties."
    )


def validate_query_schema(cleaned_query: str) -> None:
    _validate_labels(cleaned_query)
    variable_labels = _extract_variable_labels(cleaned_query)
    _validate_relationship_types(cleaned_query)
    _validate_relationship_patterns(cleaned_query, variable_labels)
    _validate_properties(cleaned_query, variable_labels)


def _validate_labels(cleaned_query: str) -> None:
    labels = re.findall(rf"\(\s*{_IDENT}\s*:\s*({_IDENT})", cleaned_query)
    for label in labels:
        if label not in QUERY_NODE_SCHEMA:
            raise ValueError(f"Cypher query uses unknown node label: {label}")


def _extract_variable_labels(cleaned_query: str) -> dict[str, set[str]]:
    variable_labels: dict[str, set[str]] = {}
    for variable, label in re.findall(
        rf"\(\s*({_IDENT})\s*:\s*({_IDENT})",
        cleaned_query,
    ):
        variable_labels.setdefault(variable, set()).add(label)
    return variable_labels


def _validate_relationship_types(cleaned_query: str) -> None:
    relationship_types = re.findall(
        rf"\[\s*(?:{_IDENT}\s*)?:\s*({_IDENT})",
        cleaned_query,
    )
    allowed_relationships = set(QUERY_RELATIONSHIP_SCHEMA)
    for relationship_type in relationship_types:
        if relationship_type not in allowed_relationships:
            raise ValueError(f"Cypher query uses unknown relationship type: {relationship_type}")


def _validate_relationship_patterns(
    cleaned_query: str,
    variable_labels: dict[str, set[str]],
) -> None:
    pattern_matches = re.finditer(
        rf"\(\s*(?P<left_var>{_IDENT})(?:\s*:\s*(?P<left_label>{_IDENT}))?[^)]*\)"
        rf"\s*(?P<left_arrow><-|-)\s*"
        rf"\[\s*(?:{_IDENT}\s*)?:\s*(?P<relationship>{_IDENT})[^\]]*\]"
        rf"\s*(?P<right_arrow>->|-)\s*"
        rf"\(\s*(?P<right_var>{_IDENT})(?:\s*:\s*(?P<right_label>{_IDENT}))?[^)]*\)",
        cleaned_query,
    )
    for match in pattern_matches:
        relationship_type = match.group("relationship")
        left_arrow = match.group("left_arrow")
        right_arrow = match.group("right_arrow")
        if left_arrow == "-" and right_arrow == "-":
            raise ValueError(
                f"Cypher query uses undirected relationship pattern for {relationship_type}; use the canonical direction."
            )
        if relationship_type in _UNRESTRICTED_RELATIONSHIP_TYPES:
            continue

        left_labels = _resolve_labels(match.group("left_var"), match.group("left_label"), variable_labels)
        right_labels = _resolve_labels(match.group("right_var"), match.group("right_label"), variable_labels)
        if not left_labels or not right_labels:
            continue

        if left_arrow == "-" and right_arrow == "->":
            source_labels = left_labels
            target_labels = right_labels
        elif left_arrow == "<-" and right_arrow == "-":
            source_labels = right_labels
            target_labels = left_labels
        else:
            raise ValueError(
                f"Cypher query uses unsupported relationship arrow syntax for {relationship_type}."
            )

        allowed_pairs = {
            (pattern.source_label, pattern.target_label)
            for pattern in QUERY_RELATIONSHIP_PATTERNS
            if pattern.relationship_type == relationship_type
        }
        if any((source_label, target_label) in allowed_pairs for source_label in source_labels for target_label in target_labels):
            continue
        raise ValueError(
            f"Cypher query uses invalid direction or endpoint labels for relationship type {relationship_type}."
        )


def _resolve_labels(variable: str, inline_label: str | None, variable_labels: dict[str, set[str]]) -> set[str]:
    labels = set(variable_labels.get(variable, set()))
    if inline_label:
        labels.add(inline_label)
    return labels


def _validate_properties(cleaned_query: str, variable_labels: dict[str, set[str]]) -> None:
    for variable, property_name in re.findall(rf"\b({_IDENT})\.({_IDENT})\b", cleaned_query):
        labels = variable_labels.get(variable)
        if not labels or len(labels) != 1:
            continue
        label = next(iter(labels))
        allowed_properties = QUERY_NODE_SCHEMA.get(label, ())
        if property_name not in allowed_properties:
            raise ValueError(f"Cypher query uses unknown property `{property_name}` for label `{label}`.")


def build_archimate_mapping_reference() -> str:
    from core.app_config import resolve_archimate_mapping_path

    mapping_path = resolve_archimate_mapping_path()
    try:
        raw = json.loads(mapping_path.read_text(encoding="utf-8"))
        import_map: dict[str, str] = raw.get("elements", {}).get("import", {})
        ignore_list: list[str] = raw.get("elements", {}).get("ignore", [])
    except Exception:
        return ""

    if not import_map:
        return ""

    rows = "\n".join(
        f"| {archimate_type:<22} | {bridgr_label} |"
        for archimate_type, bridgr_label in sorted(import_map.items())
    )
    ignore_note = ""
    if ignore_list:
        ignore_note = (
            "\n\nThe following ArchiMate types are intentionally ignored during import "
            "(silently skipped, not modeled in BRIDGR):\n"
            + ", ".join(sorted(ignore_list))
        )
    return (
        "## ArchiMate-Mapping\n\n"
        "Nodes imported from ArchiMate carry the property `archimate_type`.\n"
        "Mapping of ArchiMate framework types to BRIDGR labels:\n\n"
        "| archimate_type         | BRIDGR-Label  |\n"
        "|------------------------|---------------|\n"
        f"{rows}\n\n"
        "When a user asks for a framework type (e.g. 'all ApplicationComponents'), use the\n"
        "corresponding BRIDGR label (`:Application`). Filter on `archimate_type` only when the\n"
        "user explicitly asks about the ArchiMate origin. Not all nodes carry `archimate_type`\n"
        "— only elements imported from ArchiMate files."
        f"{ignore_note}"
    )
