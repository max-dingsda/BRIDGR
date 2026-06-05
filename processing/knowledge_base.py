from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from datetime import date
from pathlib import Path
from typing import Any, Literal, TypedDict


DEFAULT_KB_PATH = Path("knowledge_base/kb.json")


class ConfirmedLink(TypedDict):
    prozess: str
    anwendung_name: str
    cmdb_id: str
    resolved_to: str
    bestaetigt_am: str
    quelle: str


class RejectedLink(TypedDict):
    prozess: str
    anwendung_name: str
    cmdb_id: str | None
    abgelehnt_am: str


class OrgUnitEntry(TypedDict):
    name: str
    created_at: str
    source: str


class OrgUnitCandidate(TypedDict):
    candidate_name: str
    normalized_name: str
    source_paths: list[str]
    process_names: list[str]
    role_names: list[str]
    status: str
    mapped_org_unit: str
    first_seen: str
    last_seen: str


class RoleDecision(TypedDict):
    role_name: str
    normalized_name: str
    status: str
    decided_at: str


@dataclass(slots=True)
class KnowledgeBase:
    confirmed: list[ConfirmedLink]
    rejected: list[RejectedLink]
    disambiguation: list[dict[str, Any]]
    process_identity: list[dict[str, Any]]
    org_units: list[OrgUnitEntry]
    org_unit_candidates: list[OrgUnitCandidate]
    role_decisions: list[RoleDecision] = field(default_factory=list)


KnowledgeBaseSection = Literal[
    "confirmed",
    "rejected",
    "disambiguation",
    "process_identity",
    "org_units",
    "org_unit_candidates",
]


def normalize_org_unit_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def load_knowledge_base(path: Path | None = None) -> KnowledgeBase:
    kb_path = path or DEFAULT_KB_PATH
    if not kb_path.exists():
        return KnowledgeBase(
            confirmed=[],
            rejected=[],
            disambiguation=[],
            process_identity=[],
            org_units=[],
            org_unit_candidates=[],
            role_decisions=[],
        )

    with kb_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return KnowledgeBase(
        confirmed=list(payload.get("confirmed", [])),
        rejected=list(payload.get("rejected", [])),
        disambiguation=list(payload.get("disambiguation", [])),
        process_identity=list(payload.get("process_identity", [])),
        org_units=list(payload.get("org_units", [])),
        org_unit_candidates=list(payload.get("org_unit_candidates", [])),
        role_decisions=list(payload.get("role_decisions", [])),
    )


def save_knowledge_base(knowledge_base: KnowledgeBase, path: Path | None = None) -> None:
    kb_path = path or DEFAULT_KB_PATH
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    with kb_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(knowledge_base), handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def confirm_link(
    knowledge_base: KnowledgeBase,
    process_name: str,
    application_name: str,
    cmdb_id: str,
    matched_name: str,
    source: str = "manuell",
) -> KnowledgeBase:
    updated_confirmed = [
        entry
        for entry in knowledge_base.confirmed
        if not (
            entry.get("prozess") == process_name
            and entry.get("anwendung_name") == application_name
            and entry.get("cmdb_id") == cmdb_id
        )
    ]
    updated_confirmed.append(
        {
            "prozess": process_name,
            "anwendung_name": application_name,
            "cmdb_id": cmdb_id,
            "resolved_to": matched_name,
            "bestaetigt_am": date.today().isoformat(),
            "quelle": source,
        }
    )
    updated_rejected = [
        entry
        for entry in knowledge_base.rejected
        if not (
            entry.get("prozess") == process_name
            and entry.get("anwendung_name") == application_name
            and (not entry.get("cmdb_id") or entry.get("cmdb_id") == cmdb_id)
        )
    ]
    return KnowledgeBase(
        confirmed=updated_confirmed,
        rejected=updated_rejected,
        disambiguation=knowledge_base.disambiguation,
        process_identity=knowledge_base.process_identity,
        org_units=knowledge_base.org_units,
        org_unit_candidates=knowledge_base.org_unit_candidates,
        role_decisions=knowledge_base.role_decisions,
    )


def reject_link(
    knowledge_base: KnowledgeBase,
    process_name: str,
    application_name: str,
    cmdb_id: str | None = None,
) -> KnowledgeBase:
    updated_rejected = [
        entry
        for entry in knowledge_base.rejected
        if not (
            entry.get("prozess") == process_name
            and entry.get("anwendung_name") == application_name
            and entry.get("cmdb_id") == cmdb_id
        )
    ]
    updated_rejected.append(
        {
            "prozess": process_name,
            "anwendung_name": application_name,
            "cmdb_id": cmdb_id,
            "abgelehnt_am": date.today().isoformat(),
        }
    )
    updated_confirmed = [
        entry
        for entry in knowledge_base.confirmed
        if not (
            entry.get("prozess") == process_name
            and entry.get("anwendung_name") == application_name
            and (cmdb_id is None or entry.get("cmdb_id") == cmdb_id)
        )
    ]
    return KnowledgeBase(
        confirmed=updated_confirmed,
        rejected=updated_rejected,
        disambiguation=knowledge_base.disambiguation,
        process_identity=knowledge_base.process_identity,
        org_units=knowledge_base.org_units,
        org_unit_candidates=knowledge_base.org_unit_candidates,
        role_decisions=knowledge_base.role_decisions,
    )


def add_org_unit(
    knowledge_base: KnowledgeBase,
    name: str,
    source: str = "manual",
) -> KnowledgeBase:
    cleaned_name = " ".join(name.strip().split())
    if not cleaned_name:
        return knowledge_base

    normalized_name = normalize_org_unit_name(cleaned_name)
    for entry in knowledge_base.org_units:
        if normalize_org_unit_name(entry.get("name", "")) == normalized_name:
            return knowledge_base

    updated_org_units = list(knowledge_base.org_units)
    updated_org_units.append(
        {
            "name": cleaned_name,
            "created_at": date.today().isoformat(),
            "source": source,
        }
    )
    return KnowledgeBase(
        confirmed=knowledge_base.confirmed,
        rejected=knowledge_base.rejected,
        disambiguation=knowledge_base.disambiguation,
        process_identity=knowledge_base.process_identity,
        org_units=updated_org_units,
        org_unit_candidates=knowledge_base.org_unit_candidates,
        role_decisions=knowledge_base.role_decisions,
    )


def upsert_org_unit_candidate(
    knowledge_base: KnowledgeBase,
    candidate_name: str,
    source_path: str,
    process_name: str,
    role_name: str = "",
) -> KnowledgeBase:
    cleaned_name = " ".join(candidate_name.strip().split())
    if not cleaned_name:
        return knowledge_base

    normalized_name = normalize_org_unit_name(cleaned_name)
    if any(normalize_org_unit_name(entry.get("name", "")) == normalized_name for entry in knowledge_base.org_units):
        return knowledge_base

    updated_candidates = list(knowledge_base.org_unit_candidates)
    today = date.today().isoformat()
    for entry in updated_candidates:
        if entry.get("normalized_name") != normalized_name:
            continue
        if source_path and source_path not in entry["source_paths"]:
            entry["source_paths"].append(source_path)
        if process_name and process_name not in entry["process_names"]:
            entry["process_names"].append(process_name)
        if role_name and role_name not in entry["role_names"]:
            entry["role_names"].append(role_name)
        if entry.get("status") == "open":
            entry["last_seen"] = today
        return KnowledgeBase(
            confirmed=knowledge_base.confirmed,
            rejected=knowledge_base.rejected,
            disambiguation=knowledge_base.disambiguation,
            process_identity=knowledge_base.process_identity,
            org_units=knowledge_base.org_units,
            org_unit_candidates=updated_candidates,
            role_decisions=knowledge_base.role_decisions,
        )

    updated_candidates.append(
        {
            "candidate_name": cleaned_name,
            "normalized_name": normalized_name,
            "source_paths": [source_path] if source_path else [],
            "process_names": [process_name] if process_name else [],
            "role_names": [role_name] if role_name else [],
            "status": "open",
            "mapped_org_unit": "",
            "first_seen": today,
            "last_seen": today,
        }
    )
    return KnowledgeBase(
        confirmed=knowledge_base.confirmed,
        rejected=knowledge_base.rejected,
        disambiguation=knowledge_base.disambiguation,
        process_identity=knowledge_base.process_identity,
        org_units=knowledge_base.org_units,
        org_unit_candidates=updated_candidates,
        role_decisions=knowledge_base.role_decisions,
    )


def map_org_unit_candidate(
    knowledge_base: KnowledgeBase,
    candidate_name: str,
    target_org_unit: str,
) -> KnowledgeBase:
    normalized_candidate = normalize_org_unit_name(candidate_name)
    normalized_target = normalize_org_unit_name(target_org_unit)
    updated = add_org_unit(knowledge_base, target_org_unit, source="manual")
    updated_candidates = list(updated.org_unit_candidates)
    for entry in updated_candidates:
        if entry.get("normalized_name") != normalized_candidate:
            continue
        entry["status"] = "mapped"
        entry["mapped_org_unit"] = target_org_unit.strip()
        entry["last_seen"] = date.today().isoformat()
        break
    return KnowledgeBase(
        confirmed=updated.confirmed,
        rejected=updated.rejected,
        disambiguation=updated.disambiguation,
        process_identity=updated.process_identity,
        org_units=updated.org_units,
        org_unit_candidates=updated_candidates,
        role_decisions=updated.role_decisions,
    )


def accept_org_unit_candidate_as_new(
    knowledge_base: KnowledgeBase,
    candidate_name: str,
    target_name: str | None = None,
) -> KnowledgeBase:
    resolved_name = (target_name or candidate_name).strip()
    updated = add_org_unit(knowledge_base, resolved_name, source="candidate")
    return map_org_unit_candidate(updated, candidate_name, resolved_name)


def reject_org_unit_candidate(
    knowledge_base: KnowledgeBase,
    candidate_name: str,
) -> KnowledgeBase:
    normalized_candidate = normalize_org_unit_name(candidate_name)
    updated_candidates = list(knowledge_base.org_unit_candidates)
    for entry in updated_candidates:
        if entry.get("normalized_name") != normalized_candidate:
            continue
        entry["status"] = "rejected"
        entry["mapped_org_unit"] = ""
        entry["last_seen"] = date.today().isoformat()
        break
    return KnowledgeBase(
        confirmed=knowledge_base.confirmed,
        rejected=knowledge_base.rejected,
        disambiguation=knowledge_base.disambiguation,
        process_identity=knowledge_base.process_identity,
        org_units=knowledge_base.org_units,
        org_unit_candidates=updated_candidates,
        role_decisions=knowledge_base.role_decisions,
    )


def mark_role_as_explicit(
    knowledge_base: KnowledgeBase,
    role_name: str,
) -> KnowledgeBase:
    cleaned_name = " ".join(role_name.strip().split())
    if not cleaned_name:
        return knowledge_base

    normalized_name = normalize_org_unit_name(cleaned_name)
    updated_decisions = [
        entry
        for entry in knowledge_base.role_decisions
        if entry.get("normalized_name") != normalized_name
    ]
    updated_decisions.append(
        {
            "role_name": cleaned_name,
            "normalized_name": normalized_name,
            "status": "role_only",
            "decided_at": date.today().isoformat(),
        }
    )
    return KnowledgeBase(
        confirmed=knowledge_base.confirmed,
        rejected=knowledge_base.rejected,
        disambiguation=knowledge_base.disambiguation,
        process_identity=knowledge_base.process_identity,
        org_units=knowledge_base.org_units,
        org_unit_candidates=knowledge_base.org_unit_candidates,
        role_decisions=updated_decisions,
    )


def is_explicit_role(knowledge_base: KnowledgeBase, role_name: str) -> bool:
    normalized_name = normalize_org_unit_name(role_name)
    return any(
        entry.get("normalized_name") == normalized_name and entry.get("status") == "role_only"
        for entry in knowledge_base.role_decisions
    )


def clear_knowledge_base_sections(
    knowledge_base: KnowledgeBase,
    sections: set[KnowledgeBaseSection],
) -> KnowledgeBase:
    return KnowledgeBase(
        confirmed=[] if "confirmed" in sections else knowledge_base.confirmed,
        rejected=[] if "rejected" in sections else knowledge_base.rejected,
        disambiguation=[] if "disambiguation" in sections else knowledge_base.disambiguation,
        process_identity=[] if "process_identity" in sections else knowledge_base.process_identity,
        org_units=[] if "org_units" in sections else knowledge_base.org_units,
        org_unit_candidates=[] if "org_unit_candidates" in sections else knowledge_base.org_unit_candidates,
        role_decisions=knowledge_base.role_decisions,
    )
