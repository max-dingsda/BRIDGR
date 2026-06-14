from __future__ import annotations

from dataclasses import dataclass
import json
import re


# Unicode-aware identifier: starts with letter/underscore, followed by word chars.
# Necessary because BRIDGR relationship types contain umlauts (KÖNNTE_DIENEN, KÖNNTE_VERANTWORTEN).
_IDENT = r"[^\W\d]\w*"


@dataclass(frozen=True, slots=True)
class RelationshipPattern:
    relationship_type: str
    source_label: str
    target_label: str
    properties: tuple[str, ...] = ()


QUERY_NODE_SCHEMA: dict[str, tuple[str, ...]] = {
    "Prozess": ("prozess_id", "name", "archimate_type", "archimate_id"),
    "Anwendung": ("id", "cmdb_id", "name", "archimate_type", "archimate_id"),
    "Schnittstelle": ("id", "name", "archimate_type", "archimate_id"),
    "Server": ("id", "name", "server_type", "archimate_type", "archimate_id"),
    "OrgEinheit": ("name",),
    "Rolle": ("name", "archimate_type", "archimate_id", "role_only"),
    "Alias": ("normalized_name", "name", "source_kind"),
}

QUERY_RELATIONSHIP_PATTERNS: tuple[RelationshipPattern, ...] = (
    RelationshipPattern("DIENT", "Anwendung", "Prozess", ("konfidenz", "source")),
    RelationshipPattern("BETEILIGT_AN", "Rolle", "Prozess"),
    RelationshipPattern("KANN_EINNEHMEN", "OrgEinheit", "Rolle"),
    RelationshipPattern("VERANTWORTET", "OrgEinheit", "Prozess"),
    RelationshipPattern("VERANTWORTET", "OrgEinheit", "Anwendung"),
    RelationshipPattern("VERANTWORTET", "OrgEinheit", "Schnittstelle"),
    RelationshipPattern("VERANTWORTET", "OrgEinheit", "Server"),
    RelationshipPattern("FOLGT_AUF", "Prozess", "Prozess"),
    RelationshipPattern("USES_INTERFACE", "Anwendung", "Schnittstelle"),
    RelationshipPattern("RUNS_ON", "Anwendung", "Server"),
    RelationshipPattern("RUNS_ON", "Schnittstelle", "Server"),
    RelationshipPattern("KÖNNTE_DIENEN", "Anwendung", "Prozess", ("score",)),
    RelationshipPattern("KÖNNTE_VERANTWORTEN", "OrgEinheit", "Anwendung", ("score",)),
    RelationshipPattern("KÖNNTE_VERANTWORTEN", "OrgEinheit", "Schnittstelle", ("score",)),
    RelationshipPattern("KÖNNTE_VERANTWORTEN", "OrgEinheit", "Server", ("score",)),
    RelationshipPattern("KÖNNTE_VERANTWORTEN", "OrgEinheit", "Prozess", ("score",)),
    RelationshipPattern("KANN_MEINEN", "Alias", "Anwendung", ("source_kind",)),
    RelationshipPattern("KANN_MEINEN", "Alias", "OrgEinheit", ("source_kind",)),
)

QUERY_RELATIONSHIP_SCHEMA: dict[str, tuple[str, ...]] = {}
for _pattern in QUERY_RELATIONSHIP_PATTERNS:
    QUERY_RELATIONSHIP_SCHEMA.setdefault(_pattern.relationship_type, _pattern.properties)


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
    except Exception:
        return ""

    if not import_map:
        return ""

    rows = "\n".join(
        f"| {archimate_type:<22} | {bridgr_label} |"
        for archimate_type, bridgr_label in sorted(import_map.items())
    )
    return (
        "## ArchiMate-Mapping\n\n"
        "Nodes imported from ArchiMate carry the property `archimate_type`.\n"
        "Mapping of ArchiMate framework types to BRIDGR labels:\n\n"
        "| archimate_type         | BRIDGR-Label  |\n"
        "|------------------------|---------------|\n"
        f"{rows}\n\n"
        "When a user asks for a framework type (e.g. 'all ApplicationComponents'), use the\n"
        "corresponding BRIDGR label (`:Anwendung`). Filter on `archimate_type` only when the\n"
        "user explicitly asks about the ArchiMate origin. Not all nodes carry `archimate_type`\n"
        "— only elements imported from ArchiMate files."
    )
