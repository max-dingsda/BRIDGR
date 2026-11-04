from __future__ import annotations

import subprocess

import pytest

from services.graph_view_service import (
    NODE_BUDGET,
    GraphEdge,
    GraphNode,
    Seed,
    Subgraph,
    apply_node_budget,
    build_dot,
    build_subgraph,
    collect_seed_candidates,
    extract_relationship_types,
    generate_graph_dot,
    resolve_seeds,
)
from services.chat_diagram_service import _candidate, _node_visual, _renderer_evidence_dir, _renderer_failure_detail


class FakeNeo4jClient:
    """Answers reads from a queue and records what was asked."""

    def __init__(self, responses=None) -> None:
        self.responses = list(responses or [])
        self.queries: list[tuple[str, dict | None]] = []

    def execute_read(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        if self.responses:
            return self.responses.pop(0)
        return []


class SeedLookupClient:
    """Resolves seeds from a name -> rows map and returns no neighborhood."""

    def __init__(self, matches: dict[str, list[dict]]) -> None:
        self.matches = matches

    def execute_read(self, query: str, parameters=None):
        if "n.name = $value" in query:
            return list(self.matches.get((parameters or {}).get("value"), []))
        return []


# --- collect_seed_candidates ---------------------------------------------------------


def test_collect_seed_candidates_returns_distinct_scalar_strings() -> None:
    rows = [
        {"application": "SAP SD", "server": "ns-prd-001"},
        {"application": "SAP SD", "count": 3},
    ]

    assert collect_seed_candidates(rows) == ["SAP SD", "ns-prd-001"]


def test_collect_seed_candidates_drops_non_strings_blanks_and_schema_terms() -> None:
    rows = [{"a": "  ", "b": None, "c": 7, "d": ["x"], "e": "Application", "f": " SAP SD "}]

    assert collect_seed_candidates(rows) == ["SAP SD"]


def test_collect_seed_candidates_handles_empty_rows() -> None:
    assert collect_seed_candidates([]) == []


# --- resolve_seeds (seed contract) ---------------------------------------------------


def test_resolve_seeds_accepts_only_unique_matches() -> None:
    client = SeedLookupClient(
        {
            "SAP SD": [{"eid": "4:a:1", "label": "Application"}],
            "Order": [{"eid": "4:a:2", "label": "Process"}, {"eid": "4:a:3", "label": "Role"}],
            "Unknown": [],
        }
    )

    seeds = resolve_seeds(client, ["SAP SD", "Order", "Unknown"])

    assert seeds == [Seed(element_id="4:a:1", label="Application", name="SAP SD")]


def test_resolve_seeds_restricts_the_lookup_to_business_labels() -> None:
    client = FakeNeo4jClient([[]])

    resolve_seeds(client, ["Buchhaltung"])

    _, parameters = client.queries[0]
    assert "Alias" not in parameters["visual_labels"]
    assert "ManualDecision" not in parameters["visual_labels"]
    assert "OrgCandidate" not in parameters["visual_labels"]
    assert "Application" in parameters["visual_labels"]


def test_resolve_seeds_deduplicates_candidates_pointing_at_the_same_node() -> None:
    client = SeedLookupClient(
        {
            "SAP SD": [{"eid": "4:a:1", "label": "Application"}],
            "SAP Sales": [{"eid": "4:a:1", "label": "Application"}],
        }
    )

    seeds = resolve_seeds(client, ["SAP SD", "SAP Sales"])

    assert [seed.element_id for seed in seeds] == ["4:a:1"]


def test_generate_graph_dot_returns_no_diagram_without_resolved_seeds() -> None:
    client = SeedLookupClient({})

    result = generate_graph_dot(client, [{"application": "SAP SD"}], "MATCH (a:Application) RETURN a.name")

    assert result.dot is None
    assert result.truncated is False


# --- extract_relationship_types ------------------------------------------------------


def test_extract_relationship_types_returns_the_used_business_types() -> None:
    query = "MATCH (a:Application)-[:SERVES]->(p:Process)<-[:PARTICIPATES_IN]-(r:Role) RETURN p.name"

    assert extract_relationship_types(query) == ["SERVES", "PARTICIPATES_IN"]


def test_extract_relationship_types_ignores_types_inside_string_literals() -> None:
    query = "MATCH (p:Process) WHERE p.name = 'uses [:RUNS_ON] internally' RETURN p.name"

    assert extract_relationship_types(query) == []


def test_extract_relationship_types_drops_weak_and_unknown_types() -> None:
    query = "MATCH (a:Application)-[:MAY_SERVE]->(p:Process) RETURN p.name"

    assert extract_relationship_types(query) == []


def test_extract_relationship_types_returns_empty_for_aggregate_queries() -> None:
    assert extract_relationship_types("MATCH (p:Process) RETURN count(p) AS total") == []
    assert extract_relationship_types("") == []


# --- build_subgraph ------------------------------------------------------------------


def _seed() -> Seed:
    return Seed(element_id="s1", label="Server", name="ns-prd-001")


def test_build_subgraph_expands_along_the_used_types_only() -> None:
    client = FakeNeo4jClient(
        [
            [
                {
                    "source_eid": "s1",
                    "target_eid": "a1",
                    "relationship_type": "RUNS_ON",
                    "outgoing": False,
                    "target_label": "Application",
                    "target_name": "SAP SD",
                }
            ],
            [],
            [],
        ]
    )

    subgraph = build_subgraph(client, [_seed()], ["RUNS_ON"])

    assert set(subgraph.nodes) == {"s1", "a1"}
    # Direction is restored from startNode(r): Application -> Server.
    assert subgraph.edges == [GraphEdge("a1", "s1", "RUNS_ON")]
    expansion_parameters = client.queries[0][1]
    assert expansion_parameters["relationship_types"] == ["RUNS_ON"]


def test_build_subgraph_falls_back_to_two_hops_without_usable_types() -> None:
    client = FakeNeo4jClient(
        [
            [
                {
                    "source_eid": "s1",
                    "target_eid": "a1",
                    "relationship_type": "RUNS_ON",
                    "outgoing": False,
                    "target_label": "Application",
                    "target_name": "SAP SD",
                }
            ],
            [
                {
                    "source_eid": "a1",
                    "target_eid": "p1",
                    "relationship_type": "SERVES",
                    "outgoing": True,
                    "target_label": "Process",
                    "target_name": "Order",
                }
            ],
            [],
        ]
    )

    subgraph = build_subgraph(client, [_seed()], [])

    assert set(subgraph.nodes) == {"s1", "a1", "p1"}
    assert "SERVES" in client.queries[0][1]["relationship_types"]
    assert "MAY_SERVE" not in client.queries[0][1]["relationship_types"]
    # Two expansion rounds plus the weak-edge decoration query.
    assert len(client.queries) == 3


def test_build_subgraph_skips_excluded_labels_in_raw_results() -> None:
    client = FakeNeo4jClient(
        [
            [
                {
                    "source_eid": "s1",
                    "target_eid": "x1",
                    "relationship_type": "RUNS_ON",
                    "outgoing": False,
                    "target_label": "Alias",
                    "target_name": "ns prd 001",
                }
            ],
            [],
        ]
    )

    subgraph = build_subgraph(client, [_seed()], ["RUNS_ON"])

    assert set(subgraph.nodes) == {"s1"}
    assert subgraph.edges == []


def test_build_subgraph_adds_weak_edges_between_collected_nodes_only() -> None:
    client = FakeNeo4jClient(
        [
            [
                {
                    "source_eid": "s1",
                    "target_eid": "a1",
                    "relationship_type": "RUNS_ON",
                    "outgoing": False,
                    "target_label": "Application",
                    "target_name": "SAP SD",
                }
            ],
            [],
            [
                {"source_eid": "a1", "target_eid": "s1", "relationship_type": "MAY_SERVE"},
                {"source_eid": "a1", "target_eid": "p9", "relationship_type": "MAY_SERVE"},
            ],
        ]
    )

    subgraph = build_subgraph(client, [_seed()], ["RUNS_ON"])

    assert "p9" not in subgraph.nodes
    assert GraphEdge("a1", "s1", "MAY_SERVE") in subgraph.edges
    assert all(edge.target_id != "p9" for edge in subgraph.edges)


def test_build_subgraph_uses_the_element_id_tail_when_a_node_has_no_name() -> None:
    client = FakeNeo4jClient(
        [
            [
                {
                    "source_eid": "s1",
                    "target_eid": "4:db:77",
                    "relationship_type": "RUNS_ON",
                    "outgoing": False,
                    "target_label": "Application",
                    "target_name": None,
                }
            ],
            [],
        ]
    )

    subgraph = build_subgraph(client, [_seed()], ["RUNS_ON"])

    assert subgraph.nodes["4:db:77"].name == "77"


def test_build_subgraph_returns_nothing_without_seeds() -> None:
    client = FakeNeo4jClient()

    subgraph = build_subgraph(client, [], ["RUNS_ON"])

    assert subgraph.nodes == {}
    assert client.queries == []


# --- apply_node_budget ---------------------------------------------------------------


def _ring_subgraph(ring_sizes: list[int]) -> Subgraph:
    subgraph = Subgraph()
    counter = 0
    for depth, size in enumerate(ring_sizes):
        for _ in range(size):
            element_id = f"n{counter}"
            subgraph.nodes[element_id] = GraphNode(element_id, "Process", element_id, depth)
            if depth:
                subgraph.edges.append(GraphEdge("n0", element_id, "FOLLOWS"))
            counter += 1
    return subgraph


def test_apply_node_budget_keeps_a_graph_that_exactly_fits() -> None:
    subgraph, truncated = apply_node_budget(_ring_subgraph([1, NODE_BUDGET - 1]))

    assert truncated is False
    assert len(subgraph.nodes) == NODE_BUDGET


def test_apply_node_budget_drops_the_whole_ring_that_exceeds_the_budget() -> None:
    subgraph, truncated = apply_node_budget(_ring_subgraph([1, NODE_BUDGET - 1, 1]))

    assert truncated is True
    assert len(subgraph.nodes) == NODE_BUDGET
    assert all(node.depth <= 1 for node in subgraph.nodes.values())


def test_apply_node_budget_drops_edges_pointing_at_removed_nodes() -> None:
    subgraph, truncated = apply_node_budget(_ring_subgraph([1, NODE_BUDGET]))

    assert truncated is True
    assert len(subgraph.nodes) == 1
    assert subgraph.edges == []


def test_apply_node_budget_handles_an_empty_subgraph() -> None:
    subgraph, truncated = apply_node_budget(Subgraph())

    assert truncated is False
    assert subgraph.nodes == {}


# --- build_dot -----------------------------------------------------------------------


def _small_subgraph() -> Subgraph:
    subgraph = Subgraph()
    subgraph.nodes["s1"] = GraphNode("s1", "Server", "ns-prd-001", 0)
    subgraph.nodes["a1"] = GraphNode("a1", "Application", "SAP SD", 1)
    subgraph.nodes["p1"] = GraphNode("p1", "Process", "Order", 2)
    subgraph.edges.append(GraphEdge("a1", "s1", "RUNS_ON"))
    subgraph.edges.append(GraphEdge("a1", "p1", "MAY_SERVE"))
    return subgraph


def test_build_dot_colors_nodes_by_type_and_highlights_the_seed() -> None:
    dot = build_dot(_small_subgraph(), False, [_seed()], dark_mode=False, locale="de")

    assert "rankdir=LR" in dot
    assert '#eae6f8' in dot  # Server fill, light theme
    assert '#dcf5fb' in dot  # Application fill, light theme
    assert 'color="#14c4e0"' in dot  # seed border
    assert "penwidth=2.4" in dot


def test_build_dot_uses_the_dark_palette_in_dark_mode() -> None:
    dot = build_dot(_small_subgraph(), False, [_seed()], dark_mode=True, locale="de")

    assert '#2c2350' in dot  # Server fill, dark theme
    assert '#eae6f8' not in dot
    assert 'color="#2fd6ef"' in dot


def test_build_dot_draws_weak_edges_dashed_and_labels_relationships() -> None:
    dot = build_dot(_small_subgraph(), False, [_seed()], dark_mode=False, locale="de")

    dashed_lines = [line for line in dot.splitlines() if "style=dashed" in line]
    assert len(dashed_lines) == 1
    assert "könnte unterstützen" in dashed_lines[0]
    assert "läuft auf" in dot


def test_build_dot_adds_a_neutral_truncation_hint_without_a_number() -> None:
    dot = build_dot(_small_subgraph(), True, [_seed()], dark_mode=False, locale="de")

    assert "Weitere Knoten ausgeblendet" in dot
    assert not any(character.isdigit() for character in "Weitere Knoten ausgeblendet")
    hint_line = [line for line in dot.splitlines() if "Weitere Knoten" in line][0]
    assert "30" not in hint_line


def test_build_dot_escapes_quotes_in_node_names() -> None:
    subgraph = Subgraph()
    subgraph.nodes["n1"] = GraphNode("n1", "Process", 'Order "Fast Lane"', 0)

    dot = build_dot(subgraph, False, [], dark_mode=False, locale="en")

    assert '\\"Fast Lane\\"' in dot


def test_build_dot_returns_none_for_an_empty_subgraph() -> None:
    assert build_dot(Subgraph(), False, [], dark_mode=False, locale="de") is None


# --- facade --------------------------------------------------------------------------


def test_generate_graph_dot_builds_a_diagram_end_to_end() -> None:
    class Client:
        def execute_read(self, query: str, parameters=None):
            if "n.name = $value" in query:
                return [{"eid": "s1", "label": "Server"}]
            if "MAY_SERVE" in query:
                return []
            if parameters and parameters.get("element_ids") == ["s1"]:
                return [
                    {
                        "source_eid": "s1",
                        "target_eid": "a1",
                        "relationship_type": "RUNS_ON",
                        "outgoing": False,
                        "target_label": "Application",
                        "target_name": "SAP SD",
                    }
                ]
            return []

    result = generate_graph_dot(
        Client(),
        [{"server": "ns-prd-001"}],
        "MATCH (a:Application)-[:RUNS_ON]->(s:Server) RETURN s.name AS server",
        dark_mode=False,
        locale="de",
    )

    assert result.dot is not None
    assert "SAP SD" in result.dot
    assert "ns-prd-001" in result.dot
    assert result.truncated is False
    assert result.note is None


def test_generate_graph_dot_returns_no_diagram_for_rows_without_candidates() -> None:
    class Client:
        def execute_read(self, query: str, parameters=None):  # pragma: no cover - not reached
            raise AssertionError("no database access expected")

    result = generate_graph_dot(Client(), [{"total": 5}], "MATCH (p:Process) RETURN count(p) AS total")

    assert result.dot is None


def test_chat_diagram_candidate_widens_components_for_long_business_names() -> None:
    nodes = {
        "process": GraphNode("process", "Process", "Eingangsrechnung prüfen und buchen", 0),
        "application": GraphNode("application", "Application", "DATEV Unternehmen Online", 0),
    }

    candidate = _candidate(
        nodes,
        [GraphEdge("application", "process", "SERVES")],
        truncated=False,
    )

    process_component = next(item for item in candidate["components"] if item["id"] == "n0")
    assert process_component["size"][0] >= 246
    assert candidate["layout"]["cellW"] >= process_component["size"][0]
    assert candidate["layout"]["cols"] <= 4


@pytest.mark.parametrize(
    ("label", "component_type", "sublabel", "icon"),
    [
        ("Process", "cloud", "Business Process", "active"),
        ("OrgUnit", "cloud", "Actor", "person"),
        ("Role", "cloud", "Actor", "person"),
        ("Application", "frontend", "Application Component", "backend"),
        ("Interface", "frontend", "Application Interface", "messagebus"),
        ("Server", "backend", "Node", "cloud"),
        ("FutureLabel", "backend", "", "none"),
    ],
)
def test_chat_diagram_node_visuals_are_independent_from_archify_types(
    label: str,
    component_type: str,
    sublabel: str,
    icon: str,
) -> None:
    visual = _node_visual(label)

    assert visual.component_type == component_type
    assert visual.sublabel == sublabel
    assert visual.icon == icon


def test_chat_diagram_candidate_applies_the_archimate_oriented_node_visuals() -> None:
    nodes = {
        "process": GraphNode("process", "Process", "Bestellung auslösen", 0),
        "application": GraphNode("application", "Application", "EDI Gateway", 0),
        "interface": GraphNode("interface", "Interface", "EDI API", 0),
        "server": GraphNode("server", "Server", "ns-prd-001", 0),
        "org": GraphNode("org", "OrgUnit", "Buchhaltung", 0),
        "role": GraphNode("role", "Role", "Sachbearbeitung", 0),
    }

    candidate = _candidate(nodes, [], truncated=False)

    assert [(item["type"], item["sublabel"], item["icon"]) for item in candidate["components"]] == [
        ("cloud", "Business Process", "active"),
        ("frontend", "Application Component", "backend"),
        ("frontend", "Application Interface", "messagebus"),
        ("backend", "Node", "cloud"),
        ("cloud", "Actor", "person"),
        ("cloud", "Actor", "person"),
    ]
    assert candidate["meta"]["legend"]["entries"] == {
        "cloud": {"label": "Business Layer"},
        "frontend": {"label": "Application Layer"},
        "backend": {"label": "Technology Layer"},
    }


def test_renderer_evidence_dir_changes_with_the_candidate_content(tmp_path) -> None:
    first = _renderer_evidence_dir(tmp_path, '{"version": 1}')
    second = _renderer_evidence_dir(tmp_path, '{"version": 2}')

    assert first.parent == tmp_path / "evidence"
    assert first != second


def test_renderer_failure_detail_prefers_archify_diagnostics() -> None:
    completed = subprocess.CompletedProcess(
        args=["archify"],
        returncode=1,
        stdout='{"diagnostics": [{"message": "The candidate has an invalid icon."}]}',
        stderr="fallback error",
    )

    assert _renderer_failure_detail(completed) == "The candidate has an invalid icon."
