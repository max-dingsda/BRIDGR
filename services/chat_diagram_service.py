"""Local Archify artifacts for a persisted chat result.

The data shaping stays in ``graph_view_service``: it only uses already persisted
result rows plus bounded, read-only neighborhood lookups.  This module never
interprets LLM output and invokes the local renderer without a shell.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from services.graph_view_service import (
    GraphEdge,
    GraphNode,
    apply_node_budget,
    build_subgraph,
    collect_seed_candidates,
    extract_relationship_types,
    resolve_seeds,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ARCHIFY_CLI = _PROJECT_ROOT / ".agents" / "skills" / "archify" / "bin" / "archify.mjs"
if not _ARCHIFY_CLI.exists():
    _ARCHIFY_CLI = Path(r"C:\Users\mgoum\.agents\skills\archify\bin\archify.mjs")
_NODE_COMMAND = "node"
_RENDER_TIMEOUT_SECONDS = 30
_LABEL_HORIZONTAL_PADDING = 22
_LABEL_WIDTH_PER_CHARACTER = 7
_MIN_COMPONENT_WIDTH = 160
_MAX_DIAGRAM_WIDTH = 1200
_GRID_GAP_X = 70
_GRID_GAP_Y = 65


@dataclass(frozen=True, slots=True)
class DiagramArtifact:
    html_path: str | None
    png_path: str | None
    note: str | None


@dataclass(frozen=True, slots=True)
class NodeVisual:
    """Presentation semantics kept separate from the Archify color type."""

    component_type: str
    sublabel: str
    icon: str


_NODE_VISUALS = {
    # Business layer
    "Process": NodeVisual("cloud", "Business Process", "active"),
    "OrgUnit": NodeVisual("cloud", "Actor", "person"),
    "Role": NodeVisual("cloud", "Actor", "person"),
    # Application layer
    "Application": NodeVisual("frontend", "Application Component", "backend"),
    "Interface": NodeVisual("frontend", "Application Interface", "messagebus"),
    # Technology layer and unknown future labels
    "Server": NodeVisual("backend", "Node", "cloud"),
}
_DEFAULT_NODE_VISUAL = NodeVisual("backend", "", "none")


def diagram_is_possible(rows: list[dict]) -> bool:
    return bool(collect_seed_candidates(rows))


def render_chat_diagram(neo4j_client, rows: list[dict], cypher_query: str, message_id: str) -> DiagramArtifact:
    """Render a validated local architecture view for one stored chat message."""
    seeds = resolve_seeds(neo4j_client, collect_seed_candidates(rows))
    if not seeds:
        return DiagramArtifact(None, None, None)
    subgraph = build_subgraph(neo4j_client, seeds, extract_relationship_types(cypher_query))
    subgraph, truncated = apply_node_budget(subgraph)
    if not subgraph.nodes:
        return DiagramArtifact(None, None, None)

    safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", message_id)[:80] or "message"
    artifact_dir = (_PROJECT_ROOT / "Output" / "chat-diagrams" / safe_id).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = artifact_dir / "candidate.json"
    html_path = artifact_dir / "diagram.html"
    candidate_json = json.dumps(_candidate(subgraph.nodes, subgraph.edges, truncated), ensure_ascii=False, indent=2)
    candidate_path.write_text(candidate_json, encoding="utf-8")
    evidence_dir = _renderer_evidence_dir(artifact_dir, candidate_json)

    if not _ARCHIFY_CLI.is_file():
        raise RuntimeError("Der lokale Archify-Renderer ist nicht verfügbar.")
    command = [
        _NODE_COMMAND,
        str(_ARCHIFY_CLI),
        "finalize",
        "architecture",
        str(candidate_path),
        str(html_path),
        "--quality",
        "showcase",
        "--json",
        "--out-dir",
        str(evidence_dir),
    ]
    try:
        completed = subprocess.run(command, cwd=_PROJECT_ROOT, capture_output=True, text=True, timeout=_RENDER_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Das lokale Diagramm konnte nicht rechtzeitig erzeugt werden.") from exc
    if completed.returncode:
        raise RuntimeError(f"Die lokale Archify-Prüfung des Diagramms ist fehlgeschlagen: {_renderer_failure_detail(completed)}")
    preview_dir = evidence_dir / "preview"
    try:
        preview = subprocess.run(
            [_NODE_COMMAND, str(_ARCHIFY_CLI), "visual-check", str(html_path), "--json", "--out-dir", str(preview_dir)],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=_RENDER_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        preview = None
    png_path = preview_dir / "diagram.visual-check.1440x900.light.png"
    if preview is None or preview.returncode or not png_path.is_file():
        png_path = Path()
    return DiagramArtifact(str(html_path), str(png_path) if png_path.is_file() else None, "Weitere Knoten ausgeblendet – Frage eingrenzen" if truncated else None)


def _renderer_evidence_dir(artifact_dir: Path, candidate_json: str) -> Path:
    """Keep renderer evidence immutable when a stored chat answer is rendered again."""
    fingerprint = hashlib.sha256(candidate_json.encode("utf-8")).hexdigest()[:12]
    return artifact_dir / "evidence" / fingerprint


def _renderer_failure_detail(completed: subprocess.CompletedProcess[str]) -> str:
    """Return Archify's first diagnostic instead of an opaque subprocess failure."""
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    diagnostics = payload.get("diagnostics", [])
    if diagnostics and isinstance(diagnostics[0], dict):
        message = diagnostics[0].get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return completed.stderr.strip() or "Keine weitere Diagnose vom Renderer erhalten."


def _candidate(nodes: dict[str, GraphNode], edges: list[GraphEdge], truncated: bool) -> dict:
    ids = {element_id: f"n{index}" for index, element_id in enumerate(nodes)}
    component_width = max((_component_width(node.name) for node in nodes.values()), default=_MIN_COMPONENT_WIDTH)
    columns = _grid_columns(len(nodes), component_width)
    components = []
    for index, node in enumerate(nodes.values()):
        visual = _node_visual(node.label)
        components.append(
            {
                "id": ids[node.element_id],
                "type": visual.component_type,
                "label": node.name,
                "sublabel": visual.sublabel,
                "icon": visual.icon,
                "row": index // columns,
                "col": index % columns,
                "size": [_component_width(node.name), 80],
            }
        )
    connections = []
    for index, edge in enumerate(edges):
        if edge.source_id in ids and edge.target_id in ids:
            connections.append({"id": f"e{index}", "from": ids[edge.source_id], "to": ids[edge.target_id], "label": "unbestätigter Kandidat" if edge.relationship_type == "MAY_SERVE" else edge.relationship_type, "variant": "dashed" if edge.relationship_type == "MAY_SERVE" else "default"})
    subtitle = "Aus der gespeicherten, geprüften Chat-Antwort" + (" · Weitere Knoten ausgeblendet" if truncated else "")
    return {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": {
            "title": "Zusammenhang der Chat-Antwort",
            "subtitle": subtitle,
            "output": "diagram.html",
            "locale": "de",
            "quality_profile": "showcase",
            "legend": {
                "entries": {
                    "cloud": {"label": "Business Layer"},
                    "frontend": {"label": "Application Layer"},
                    "backend": {"label": "Technology Layer"},
                }
            },
        },
        "layout": {"mode": "grid", "cols": columns, "gapX": _GRID_GAP_X, "gapY": _GRID_GAP_Y, "cellW": component_width, "cellH": 80},
        "components": components,
        "connections": connections,
    }


def _component_width(label: str) -> int:
    return max(_MIN_COMPONENT_WIDTH, len(label) * _LABEL_WIDTH_PER_CHARACTER + _LABEL_HORIZONTAL_PADDING)


def _grid_columns(node_count: int, component_width: int) -> int:
    if not node_count:
        return 1
    available_columns = max(1, (_MAX_DIAGRAM_WIDTH + _GRID_GAP_X) // (component_width + _GRID_GAP_X))
    return min(node_count, available_columns, 4)


def _node_visual(label: str) -> NodeVisual:
    return _NODE_VISUALS.get(label, _DEFAULT_NODE_VISUAL)
