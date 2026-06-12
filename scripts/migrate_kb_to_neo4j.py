from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.app_config import load_config
from core.env_loader import load_env_files
from processing.knowledge_base import DEFAULT_KB_PATH, load_knowledge_base
from processing.pipeline import build_neo4j_client
from services.alias_service import sync_knowledge_base_aliases


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate curated BRIDGR knowledge-base entries from kb.json into Neo4j."
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
        help="Path to the knowledge base JSON file.",
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
    knowledge_base = load_knowledge_base(args.kb_path)

    summary = build_summary(knowledge_base)
    if args.summary_only:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    neo4j_client = build_neo4j_client(config)
    try:
        synced_org_units = sync_org_units(neo4j_client, knowledge_base.org_units)
        synced_dient = migrate_confirmed_dient_edges(neo4j_client, knowledge_base.confirmed)
        synced_ablehnung = migrate_rejected_decisions(neo4j_client, knowledge_base.rejected)
        synced_aliases = sync_knowledge_base_aliases(neo4j_client, knowledge_base)
    finally:
        neo4j_client.close()

    result = {
        "kb_path": str(args.kb_path),
        "neo4j_url": config.neo4j_url,
        "neo4j_database": config.neo4j_database,
        "synced_org_units": synced_org_units,
        "synced_dient_edges": synced_dient,
        "synced_ablehnung_nodes": synced_ablehnung,
        "synced_aliases": synced_aliases,
        "skipped_sections": summary["skipped_sections"],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def build_summary(knowledge_base) -> dict:
    manual_application_aliases = 0
    for entry in knowledge_base.confirmed:
        alias_name = str(entry.get("anwendung_name", "")).strip()
        resolved_name = str(entry.get("resolved_to", "")).strip()
        cmdb_id = str(entry.get("cmdb_id", "")).strip()
        if alias_name and resolved_name and cmdb_id and alias_name.casefold() != resolved_name.casefold():
            manual_application_aliases += 1

    mapped_org_aliases = 0
    for entry in knowledge_base.org_unit_candidates:
        alias_name = str(entry.get("candidate_name", "")).strip()
        target_name = str(entry.get("mapped_org_unit", "")).strip()
        if (
            entry.get("status") == "mapped"
            and alias_name
            and target_name
            and alias_name.casefold() != target_name.casefold()
        ):
            mapped_org_aliases += 1

    return {
        "org_units": len([e for e in knowledge_base.org_units if str(e.get("name", "")).strip()]),
        "confirmed_dient_edges": len([e for e in knowledge_base.confirmed if e.get("cmdb_id")]),
        "rejected_ablehnung_nodes": len([e for e in knowledge_base.rejected if not e.get("cmdb_id")]),
        "manual_application_aliases": manual_application_aliases,
        "mapped_org_aliases": mapped_org_aliases,
        "skipped_sections": {
            "open_org_unit_candidates": len(
                [e for e in knowledge_base.org_unit_candidates if e.get("status") != "mapped"]
            ),
            "role_decisions": len(knowledge_base.role_decisions) if hasattr(knowledge_base, "role_decisions") else 0,
        },
    }


def sync_org_units(neo4j_client, org_units: list[dict]) -> int:
    written = 0
    neo4j_client.ensure_constraints()
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


def migrate_confirmed_dient_edges(neo4j_client, confirmed: list[dict]) -> int:
    """Set raw_name and source on existing DIENT edges from confirmed kb.json entries.

    Without this migration, get_confirmed_links_from_neo4j() cannot find these
    decisions because it filters on r.raw_name IS NOT NULL.
    """
    written = 0
    for entry in confirmed:
        prozess_name = str(entry.get("prozess", "")).strip()
        anwendung_name = str(entry.get("anwendung_name", "")).strip()
        cmdb_id = str(entry.get("cmdb_id", "")).strip()
        resolved_to = str(entry.get("resolved_to", anwendung_name)).strip()
        quelle = str(entry.get("quelle", "manuell_bestaetigt")).strip()

        if not prozess_name or not cmdb_id:
            continue

        # MERGE the DIENT edge (creates it if missing) and set the new properties
        neo4j_client.execute_write(
            """
            MERGE (p:Prozess {name: $prozess_name})
            MERGE (a:Anwendung {cmdb_id: $cmdb_id})
            ON CREATE SET a.name = $resolved_to, a.id = $cmdb_id
            MERGE (a)-[r:DIENT]->(p)
            SET r.konfidenz  = 'stark',
                r.raw_name   = $raw_name,
                r.source     = $source
            """,
            {
                "prozess_name": prozess_name,
                "cmdb_id": cmdb_id,
                "resolved_to": resolved_to,
                "raw_name": anwendung_name,
                "source": quelle,
            },
        )
        written += 1
    return written


def migrate_rejected_decisions(neo4j_client, rejected: list[dict]) -> int:
    """Create (:Ablehnung) nodes for name-level rejections from kb.json."""
    written = 0
    for entry in rejected:
        prozess_name = str(entry.get("prozess", "")).strip()
        anwendung_name = str(entry.get("anwendung_name", "")).strip()
        if not prozess_name or not anwendung_name or entry.get("cmdb_id"):
            # cmdb_id-level rejections are handled by the matching loop; skip here
            continue
        neo4j_client.execute_write(
            "MERGE (ab:Ablehnung {prozess_name: $prozess_name, anwendung_name: $anwendung_name})",
            {"prozess_name": prozess_name, "anwendung_name": anwendung_name},
        )
        written += 1
    return written


if __name__ == "__main__":
    raise SystemExit(main())
