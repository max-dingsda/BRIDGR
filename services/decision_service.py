from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from core.neo4j_utils import Neo4jClient


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ManualDecision:
    decision_id: str
    decision_type: str
    status: str
    created_at: str
    payload_json: str
    supersedes_decision_id: str | None = None
    reverted_at: str | None = None
    notes: str | None = None


def create_manual_decision(
    neo4j_client: Neo4jClient,
    decision_type: str,
    payload: dict[str, Any],
    *,
    status: str = "active",
    supersedes_decision_id: str | None = None,
    notes: str | None = None,
) -> ManualDecision:
    decision = ManualDecision(
        decision_id=str(uuid4()),
        decision_type=decision_type,
        status=status,
        created_at=_utc_now_iso(),
        payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        supersedes_decision_id=supersedes_decision_id,
        notes=notes,
    )
    neo4j_client.execute_write(
        """
        CREATE (d:ManualDecision {
            decision_id: $decision_id,
            decision_type: $decision_type,
            status: $status,
            created_at: $created_at,
            payload_json: $payload_json,
            supersedes_decision_id: $supersedes_decision_id,
            notes: $notes
        })
        """,
        {
            "decision_id": decision.decision_id,
            "decision_type": decision.decision_type,
            "status": decision.status,
            "created_at": decision.created_at,
            "payload_json": decision.payload_json,
            "supersedes_decision_id": decision.supersedes_decision_id,
            "notes": decision.notes,
        },
    )
    return decision


def get_manual_decision(neo4j_client: Neo4jClient, decision_id: str) -> ManualDecision | None:
    rows = neo4j_client.execute_read_unvalidated(
        """
        MATCH (d:ManualDecision {decision_id: $decision_id})
        RETURN d.decision_id AS decision_id,
               d.decision_type AS decision_type,
               d.status AS status,
               d.created_at AS created_at,
               d.payload_json AS payload_json,
               d.supersedes_decision_id AS supersedes_decision_id,
               d.reverted_at AS reverted_at,
               d.notes AS notes
        LIMIT 1
        """,
        {"decision_id": decision_id},
    )
    if not rows:
        return None
    return _row_to_manual_decision(rows[0])


def list_recent_manual_decisions(neo4j_client: Neo4jClient, limit: int = 20) -> list[ManualDecision]:
    rows = neo4j_client.execute_read_unvalidated(
        """
        MATCH (d:ManualDecision)
        RETURN d.decision_id AS decision_id,
               d.decision_type AS decision_type,
               d.status AS status,
               d.created_at AS created_at,
               d.payload_json AS payload_json,
               d.supersedes_decision_id AS supersedes_decision_id,
               d.reverted_at AS reverted_at,
               d.notes AS notes
        ORDER BY d.created_at DESC
        LIMIT $limit
        """,
        {"limit": int(limit)},
    )
    return [_row_to_manual_decision(row) for row in rows]


def mark_manual_decision_reverted(
    neo4j_client: Neo4jClient,
    decision_id: str,
    *,
    status: str = "reverted",
) -> str:
    reverted_at = _utc_now_iso()
    neo4j_client.execute_write(
        """
        MATCH (d:ManualDecision {decision_id: $decision_id})
        SET d.status = $status,
            d.reverted_at = $reverted_at
        """,
        {
            "decision_id": decision_id,
            "status": status,
            "reverted_at": reverted_at,
        },
    )
    return reverted_at


def _row_to_manual_decision(row: dict[str, Any]) -> ManualDecision:
    return ManualDecision(
        decision_id=str(row.get("decision_id", "")),
        decision_type=str(row.get("decision_type", "")),
        status=str(row.get("status", "")),
        created_at=str(row.get("created_at", "")),
        payload_json=str(row.get("payload_json", "")),
        supersedes_decision_id=row.get("supersedes_decision_id"),
        reverted_at=row.get("reverted_at"),
        notes=row.get("notes"),
    )
