from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.app_config import load_config
from core.env_loader import load_env_files
from processing.pipeline import build_neo4j_client
from services.alias_service import sync_curated_aliases
from skills.graph_writer import GraphWriter

DEFAULT_KB_PATH = Path("knowledge_base/kb.json")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "One-off migration of the retired knowledge_base/kb.json into Neo4j: "
            "org_units become (:OrgEinheit) nodes, org_unit_candidates become (:OrgKandidat) nodes."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.json"),
        help="Path to the BRIDGR config file.",
    )
    parser.add_argument(
        "--kb-path",
        type=Path,
        default=DEFAULT_KB_PATH,
        help="Path to the kb.json file to migrate.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print what would be migrated without writing to Neo4j.",
    )
    return parser


def main() -> int:
    load_env_files()
    args = build_argument_parser().parse_args()
    config = load_config(args.config)
    kb_payload = load_kb_payload(args.kb_path)

    org_units = list(kb_payload.get("org_units", []))
    org_unit_candidates = list(kb_payload.get("org_unit_candidates", []))

    if args.summary_only:
        print(json.dumps(
            {
                "kb_path": str(args.kb_path),
                "org_units": len([e for e in org_units if str(e.get("name", "")).strip()]),
                "org_unit_candidates": len(org_unit_candidates),
            },
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    neo4j_client = build_neo4j_client(config)
    graph_writer = GraphWriter()
    try:
        neo4j_client.ensure_constraints()
        synced_org_units = sync_org_units(neo4j_client, org_units)
        synced_candidates = sync_org_unit_candidates(neo4j_client, org_unit_candidates)
        synced_aliases = sync_curated_aliases(
            neo4j_client,
            graph_writer.get_confirmed_links_from_neo4j(neo4j_client),
            graph_writer.load_org_unit_candidates(neo4j_client),
        )
    finally:
        neo4j_client.close()

    result = {
        "kb_path": str(args.kb_path),
        "neo4j_url": config.neo4j_url,
        "neo4j_database": config.neo4j_database,
        "synced_org_units": synced_org_units,
        "synced_org_unit_candidates": synced_candidates,
        "synced_aliases": synced_aliases,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def load_kb_payload(kb_path: Path) -> dict:
    if not kb_path.exists():
        return {}
    with kb_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sync_org_units(neo4j_client, org_units: list[dict]) -> int:
    written = 0
    for entry in org_units:
        name = " ".join(str(entry.get("name", "")).strip().split())
        if not name:
            continue
        neo4j_client.execute_write(
            "MERGE (o:OrgEinheit {name: $name})",
            {"name": name},
        )
        written += 1
    return written


def sync_org_unit_candidates(neo4j_client, org_unit_candidates: list[dict]) -> int:
    """Migrate kb.json org_unit_candidates entries into (:OrgKandidat) nodes, preserving status."""
    written = 0
    for entry in org_unit_candidates:
        candidate_name = " ".join(str(entry.get("candidate_name", "")).strip().split())
        normalized_name = str(entry.get("normalized_name", "")).strip() or candidate_name.casefold()
        if not candidate_name or not normalized_name:
            continue
        neo4j_client.execute_write(
            """
            MERGE (k:OrgKandidat {normalized_name: $normalized_name})
            SET k.candidate_name = $candidate_name,
                k.status = $status,
                k.mapped_org_unit = $mapped_org_unit,
                k.source_paths = $source_paths,
                k.process_names = $process_names,
                k.role_names = $role_names,
                k.first_seen = $first_seen,
                k.last_seen = $last_seen
            """,
            {
                "normalized_name": normalized_name,
                "candidate_name": candidate_name,
                "status": str(entry.get("status", "open")),
                "mapped_org_unit": str(entry.get("mapped_org_unit", "")),
                "source_paths": list(entry.get("source_paths", [])),
                "process_names": list(entry.get("process_names", [])),
                "role_names": list(entry.get("role_names", [])),
                "first_seen": str(entry.get("first_seen", "")),
                "last_seen": str(entry.get("last_seen", "")),
            },
        )
        written += 1
    return written


if __name__ == "__main__":
    raise SystemExit(main())
