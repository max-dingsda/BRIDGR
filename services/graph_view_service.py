"""Deterministic answer-companion diagram for chat results (architecture §13.6).

The LLM only offers a diagram in prose; this module builds it. Everything here is
read-only, free of Streamlit imports, and derives its schema knowledge from
`core.graph_schema` so the diagram can never show internal labels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.graph_schema import (
    BUSINESS_RELATIONSHIP_TYPES,
    INTERNAL_NODE_LABELS,
    VISUAL_NODE_LABELS,
)
from core.i18n import translate
from core.neo4j_utils import _strip_cypher_strings_and_comments

# --- Module constants (§13.6.4, §13.6.5, §13.6.7) -----------------------------------

NODE_BUDGET = 30
ANSWER_DIAGRAM_NODE_LIMIT = 25
RANKDIR = "LR"
FALLBACK_HOPS = 2
EXCLUDED_LABELS: frozenset[str] = INTERNAL_NODE_LABELS
WEAK_TYPES: frozenset[str] = frozenset({"MAY_SERVE"})

# Fixed palette, contrast-checked against the card backgrounds #ffffff / #101d3a.
# Derived from the brand tokens in ui/layout.py, not looked up at runtime.
_NODE_COLORS_LIGHT: dict[str, tuple[str, str]] = {
    "Process": ("#e8f0ff", "#2f5fb0"),
    "Application": ("#dcf5fb", "#0e9fb8"),
    "Server": ("#eae6f8", "#6b52c4"),
    "Interface": ("#e2f4ec", "#1f9d6b"),
    "OrgUnit": ("#fbeed6", "#b9822a"),
    "Role": ("#eef1f6", "#687288"),
}
_NODE_COLORS_DARK: dict[str, tuple[str, str]] = {
    "Process": ("#1c3a63", "#5b8fd6"),
    "Application": ("#12414c", "#2fd6ef"),
    "Server": ("#2c2350", "#9a86e0"),
    "Interface": ("#123a2c", "#4fc79b"),
    "OrgUnit": ("#3a2e18", "#d9a83f"),
    "Role": ("#28304a", "#9aa7c4"),
}
_DEFAULT_COLORS_LIGHT = ("#eef1f6", "#8892a6")
_DEFAULT_COLORS_DARK = ("#1c2947", "#5a6a8c")
_FONT_COLOR_LIGHT = "#101725"
_FONT_COLOR_DARK = "#e7ebf3"
_SEED_BORDER_LIGHT = "#14c4e0"
_SEED_BORDER_DARK = "#2fd6ef"
_SEED_PENWIDTH = "2.4"

# Schema words that show up as literal result values (e.g. a column of label names)
# and must not be mistaken for business-object names.
_SCHEMA_TERMS = {
    "application",
    "process",
    "interface",
    "server",
    "orgunit",
    "role",
    "capability",
    "goal",
    "dataobject",
    "resource",
    "infrastructure",
    "risk",
}

_RELATIONSHIP_TYPE_PATTERN = re.compile(r"\[\s*(?:[A-Za-z_]\w*\s*)?:\s*([A-Z_]+)")


# --- Data model ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Seed:
    """A result value that resolved to exactly one business node."""

    element_id: str
    label: str
    name: str


@dataclass(frozen=True, slots=True)
class GraphNode:
    element_id: str
    label: str
    name: str
    depth: int


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: str
    target_id: str
    relationship_type: str


@dataclass(slots=True)
class Subgraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GraphResult:
    dot: str | None
    truncated: bool
    note: str | None


# --- Seed contract (§13.6.3) --------------------------------------------------------


def collect_seed_candidates(rows: list[dict]) -> list[str]:
    """Return distinct scalar string values from query results.

    These are candidates only. Whether a candidate becomes a seed is decided by
    `resolve_seeds` against the graph, never by the string itself.
    """
    candidates: list[str] = []
    seen: set[str] = set()
    for row in rows or []:
        for value in row.values():
            if not isinstance(value, str):
                continue
            name = value.strip()
            if not name or name.casefold() in _SCHEMA_TERMS or name in seen:
                continue
            candidates.append(name)
            seen.add(name)
    return candidates


def count_answer_nodes(rows: list[dict]) -> int:
    """Count distinct named answer objects that a companion diagram would show."""
    return len(collect_seed_candidates(rows))


def answer_diagram_is_renderable(rows: list[dict]) -> bool:
    """Return whether an answer has a readable number of named objects."""
    return 2 <= count_answer_nodes(rows) <= ANSWER_DIAGRAM_NODE_LIMIT


_RESOLVE_SEED_QUERY = (
    "MATCH (n) "
    "WHERE n.name = $value AND any(l IN labels(n) WHERE l IN $visual_labels) "
    "RETURN elementId(n) AS eid, "
    "[l IN labels(n) WHERE l IN $visual_labels][0] AS label"
)


def resolve_seeds(neo4j_client, candidates: list[str]) -> list[Seed]:
    """Resolve candidates to seeds via an exact name match on business labels.

    A candidate becomes a seed only when it matches exactly one node. Zero matches
    (a value that is not a business object) and multiple matches (an ambiguous name)
    are both discarded; guessing would produce a misleading diagram.
    """
    visual_labels = list(VISUAL_NODE_LABELS)
    seeds: list[Seed] = []
    seen_element_ids: set[str] = set()
    for candidate in candidates:
        rows = _execute_visualization_read(
            neo4j_client,
            _RESOLVE_SEED_QUERY,
            {"value": candidate, "visual_labels": visual_labels},
        )
        if len(rows) != 1:
            continue
        element_id = str(rows[0]["eid"])
        if element_id in seen_element_ids:
            continue
        seeds.append(Seed(element_id=element_id, label=str(rows[0]["label"]), name=candidate))
        seen_element_ids.add(element_id)
    return seeds


def extract_relationship_types(cypher_query: str) -> list[str]:
    """Return the confirmed relationship types the answering query actually walked.

    String literals and comments are stripped first so a type name mentioned inside a
    quoted value cannot widen the expansion.
    """
    if not cypher_query:
        return []
    cleaned = _strip_cypher_strings_and_comments(cypher_query)
    allowed = set(BUSINESS_RELATIONSHIP_TYPES)
    types: list[str] = []
    for relationship_type in _RELATIONSHIP_TYPE_PATTERN.findall(cleaned):
        if relationship_type in allowed and relationship_type not in types:
            types.append(relationship_type)
    return types


# --- Neighborhood query and BFS (§13.6.3, §13.6.4) ----------------------------------

_EXPAND_QUERY = (
    "MATCH (n)-[r]-(m) "
    "WHERE elementId(n) IN $element_ids "
    "AND type(r) IN $relationship_types "
    "AND any(l IN labels(m) WHERE l IN $visual_labels) "
    "RETURN elementId(n) AS source_eid, elementId(m) AS target_eid, "
    "type(r) AS relationship_type, startNode(r) = n AS outgoing, "
    "[l IN labels(m) WHERE l IN $visual_labels][0] AS target_label, "
    "m.name AS target_name"
)

_WEAK_EDGE_QUERY = (
    "MATCH (a)-[r:MAY_SERVE]->(b) "
    "WHERE elementId(a) IN $element_ids AND elementId(b) IN $element_ids "
    "RETURN elementId(a) AS source_eid, elementId(b) AS target_eid, "
    "type(r) AS relationship_type"
)

_ANSWER_EDGE_QUERY = (
    "MATCH (a)-[r]->(b) "
    "WHERE elementId(a) IN $element_ids AND elementId(b) IN $element_ids "
    "AND type(r) IN $relationship_types "
    "RETURN elementId(a) AS source_eid, elementId(b) AS target_eid, "
    "type(r) AS relationship_type"
)


def _execute_visualization_read(neo4j_client, query: str, parameters: dict) -> list[dict]:
    """Use the narrow fixed-query path when the chat client provides it."""
    execute = getattr(neo4j_client, "execute_visualization_read", None)
    if callable(execute):
        return execute(query, parameters)
    return neo4j_client.execute_read(query, parameters)


def build_subgraph(
    neo4j_client,
    seeds: list[Seed],
    relationship_types: list[str],
    budget: int = NODE_BUDGET,
) -> Subgraph:
    """Expand ring by ring from the seeds along the given relationship types.

    Without usable types from the answering query, expansion falls back to all
    confirmed types limited to `FALLBACK_HOPS`; otherwise depth is unbounded and only
    the node budget stops it. Weak `MAY_SERVE` edges decorate the result afterwards and
    never open a new expansion path.
    """
    subgraph = Subgraph()
    if not seeds:
        return subgraph

    if relationship_types:
        expansion_types = list(relationship_types)
        max_hops: int | None = None
    else:
        expansion_types = list(BUSINESS_RELATIONSHIP_TYPES)
        max_hops = FALLBACK_HOPS

    for seed in seeds:
        subgraph.nodes[seed.element_id] = GraphNode(
            element_id=seed.element_id,
            label=seed.label,
            name=seed.name,
            depth=0,
        )

    frontier = [seed.element_id for seed in seeds]
    seen_edges: set[tuple[str, str, str]] = set()
    depth = 0
    visual_labels = list(VISUAL_NODE_LABELS)

    while frontier and (max_hops is None or depth < max_hops):
        depth += 1
        rows = _execute_visualization_read(
            neo4j_client,
            _EXPAND_QUERY,
            {
                "element_ids": frontier,
                "relationship_types": expansion_types,
                "visual_labels": visual_labels,
            },
        )
        next_frontier: list[str] = []
        for row in _sorted_expansion_rows(rows):
            target_label = str(row.get("target_label") or "")
            if not target_label or target_label in EXCLUDED_LABELS:
                continue
            source_eid = str(row["source_eid"])
            target_eid = str(row["target_eid"])
            if target_eid not in subgraph.nodes:
                subgraph.nodes[target_eid] = GraphNode(
                    element_id=target_eid,
                    label=target_label,
                    name=_node_display_name(row.get("target_name"), target_eid),
                    depth=depth,
                )
                next_frontier.append(target_eid)
            _add_edge(
                subgraph,
                seen_edges,
                source_eid if row.get("outgoing") else target_eid,
                target_eid if row.get("outgoing") else source_eid,
                str(row["relationship_type"]),
            )
        # Stop as soon as a ring pushes the graph past the budget; apply_node_budget
        # then drops that ring again. Expanding further would only be discarded.
        if len(subgraph.nodes) > budget:
            break
        frontier = next_frontier

    _add_weak_edges(neo4j_client, subgraph, seen_edges)
    return subgraph


def build_answer_subgraph(
    neo4j_client,
    seeds: list[Seed],
    relationship_types: list[str],
) -> Subgraph:
    """Keep a chat diagram faithful to the objects returned in its answer.

    The diagram may verify direct relationships between the resolved answer nodes,
    but it must not expand the graph with neighbouring objects the answer did not
    mention.  This makes the visual a companion to the stored result rather than
    a broader graph exploration.
    """
    subgraph = Subgraph(
        nodes={
            seed.element_id: GraphNode(seed.element_id, seed.label, seed.name, 0)
            for seed in seeds
        }
    )
    if len(subgraph.nodes) < 2:
        return subgraph

    types = relationship_types or list(BUSINESS_RELATIONSHIP_TYPES)
    rows = _execute_visualization_read(
        neo4j_client,
        _ANSWER_EDGE_QUERY,
        {"element_ids": list(subgraph.nodes), "relationship_types": types},
    )
    seen_edges: set[tuple[str, str, str]] = set()
    for row in sorted(
        rows or [],
        key=lambda row: (
            str(row.get("source_eid") or ""),
            str(row.get("target_eid") or ""),
            str(row.get("relationship_type") or ""),
        ),
    ):
        source_id = str(row["source_eid"])
        target_id = str(row["target_eid"])
        if source_id in subgraph.nodes and target_id in subgraph.nodes:
            _add_edge(subgraph, seen_edges, source_id, target_id, str(row["relationship_type"]))
    return subgraph


def _sorted_expansion_rows(rows: list[dict]) -> list[dict]:
    """Sort rows so the diagram is reproducible for identical graph state."""
    return sorted(
        rows or [],
        key=lambda row: (
            str(row.get("target_label") or ""),
            str(row.get("target_name") or ""),
            str(row.get("target_eid") or ""),
            str(row.get("relationship_type") or ""),
        ),
    )


def _add_edge(
    subgraph: Subgraph,
    seen_edges: set[tuple[str, str, str]],
    source_id: str,
    target_id: str,
    relationship_type: str,
) -> None:
    key = (source_id, target_id, relationship_type)
    if key in seen_edges:
        return
    seen_edges.add(key)
    subgraph.edges.append(
        GraphEdge(source_id=source_id, target_id=target_id, relationship_type=relationship_type)
    )


def _add_weak_edges(
    neo4j_client,
    subgraph: Subgraph,
    seen_edges: set[tuple[str, str, str]],
) -> None:
    """Add MAY_SERVE edges between nodes that are already part of the subgraph."""
    element_ids = list(subgraph.nodes)
    if len(element_ids) < 2:
        return
    rows = _execute_visualization_read(
        neo4j_client,
        _WEAK_EDGE_QUERY,
        {"element_ids": element_ids},
    )
    for row in sorted(
        rows or [],
        key=lambda row: (str(row.get("source_eid") or ""), str(row.get("target_eid") or "")),
    ):
        source_eid = str(row["source_eid"])
        target_eid = str(row["target_eid"])
        if source_eid not in subgraph.nodes or target_eid not in subgraph.nodes:
            continue
        _add_edge(subgraph, seen_edges, source_eid, target_eid, str(row["relationship_type"]))


def _node_display_name(raw_name: object, element_id: str) -> str:
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()
    tail = element_id.rsplit(":", 1)[-1]
    return tail or "?"


def apply_node_budget(subgraph: Subgraph, budget: int = NODE_BUDGET) -> tuple[Subgraph, bool]:
    """Keep whole BFS rings only.

    Inner rings are kept complete; the first ring that would exceed the budget is
    dropped entirely, because a partially drawn ring suggests a boundary that does not
    exist in the graph. Returns only a truncation flag — after an aborted expansion the
    number of hidden nodes is not reliably countable.
    """
    if not subgraph.nodes:
        return subgraph, False

    kept: dict[str, GraphNode] = {}
    truncated = False
    for depth in sorted({node.depth for node in subgraph.nodes.values()}):
        ring = {
            element_id: node
            for element_id, node in subgraph.nodes.items()
            if node.depth == depth
        }
        if len(kept) + len(ring) > budget:
            truncated = True
            break
        kept.update(ring)

    if not truncated:
        return subgraph, False

    edges = [
        edge
        for edge in subgraph.edges
        if edge.source_id in kept and edge.target_id in kept
    ]
    return Subgraph(nodes=kept, edges=edges), True


# --- DOT rendering (§13.6.7) --------------------------------------------------------


def build_dot(
    subgraph: Subgraph,
    truncated: bool,
    seeds: list[Seed],
    dark_mode: bool,
    locale: str | None = None,
) -> str | None:
    """Render the subgraph as a DOT string for `st.graphviz_chart`."""
    if not subgraph.nodes:
        return None

    palette = _NODE_COLORS_DARK if dark_mode else _NODE_COLORS_LIGHT
    default_colors = _DEFAULT_COLORS_DARK if dark_mode else _DEFAULT_COLORS_LIGHT
    font_color = _FONT_COLOR_DARK if dark_mode else _FONT_COLOR_LIGHT
    seed_border = _SEED_BORDER_DARK if dark_mode else _SEED_BORDER_LIGHT
    seed_ids = {seed.element_id for seed in seeds}

    lines = [
        "digraph bridgr {",
        f"  rankdir={RANKDIR};",
        '  bgcolor="transparent";',
        f'  node [shape=box, style="filled,rounded", fontname="Helvetica", fontsize=10, fontcolor="{font_color}"];',
        f'  edge [fontname="Helvetica", fontsize=9, color="{default_colors[1]}", fontcolor="{font_color}"];',
    ]
    if truncated:
        lines.extend(
            [
                f'  label="{_escape_dot(translate("chat.diagram_truncated", locale))}";',
                "  labelloc=b;",
                f'  fontname="Helvetica"; fontsize=9; fontcolor="{font_color}";',
            ]
        )

    node_ids = {element_id: f"n{index}" for index, element_id in enumerate(subgraph.nodes)}
    for element_id, node in subgraph.nodes.items():
        fill, border = palette.get(node.label, default_colors)
        attributes = [
            f'label="{_escape_dot(node.name)}"',
            f'fillcolor="{fill}"',
            f'color="{seed_border if element_id in seed_ids else border}"',
        ]
        if element_id in seed_ids:
            attributes.append(f'penwidth={_SEED_PENWIDTH}')
            attributes.append('fontname="Helvetica-Bold"')
        lines.append(f'  {node_ids[element_id]} [{", ".join(attributes)}];')

    for edge in subgraph.edges:
        attributes = [f'label="{_escape_dot(_relationship_label(edge.relationship_type, locale))}"']
        if edge.relationship_type in WEAK_TYPES:
            attributes.append("style=dashed")
        lines.append(
            f'  {node_ids[edge.source_id]} -> {node_ids[edge.target_id]} [{", ".join(attributes)}];'
        )

    lines.append("}")
    return "\n".join(lines)


def _relationship_label(relationship_type: str, locale: str | None) -> str:
    key = f"graph.rel.{relationship_type}"
    translated = translate(key, locale)
    return relationship_type if translated == key else translated


def _escape_dot(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", " ")
    )


# --- Facade -------------------------------------------------------------------------


def generate_graph_dot(
    neo4j_client,
    rows: list[dict],
    cypher_query: str | None,
    dark_mode: bool = False,
    locale: str | None = None,
) -> GraphResult:
    """Build the answer-companion diagram for one chat message.

    Returns `dot=None` when no candidate resolves to a seed or the neighborhood stays
    empty — no diagram is better than a misleading one.
    """
    candidates = collect_seed_candidates(rows)
    if not candidates:
        return GraphResult(dot=None, truncated=False, note=None)

    seeds = resolve_seeds(neo4j_client, candidates)
    if not seeds:
        return GraphResult(dot=None, truncated=False, note=None)

    relationship_types = extract_relationship_types(cypher_query or "")
    subgraph = build_subgraph(neo4j_client, seeds, relationship_types)
    subgraph, truncated = apply_node_budget(subgraph)

    dot = build_dot(subgraph, truncated, seeds, dark_mode, locale)
    note = translate("chat.diagram_truncated", locale) if truncated else None
    return GraphResult(dot=dot, truncated=truncated, note=note)
