from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_KB_PATH = Path("knowledge_base/kb.json")


@dataclass(slots=True)
class KnowledgeBase:
    confirmed: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    disambiguation: list[dict[str, Any]]
    process_identity: list[dict[str, Any]]


def load_knowledge_base(path: Path | None = None) -> KnowledgeBase:
    kb_path = path or DEFAULT_KB_PATH
    if not kb_path.exists():
        return KnowledgeBase(
            confirmed=[],
            rejected=[],
            disambiguation=[],
            process_identity=[],
        )

    with kb_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return KnowledgeBase(
        confirmed=list(payload.get("confirmed", [])),
        rejected=list(payload.get("rejected", [])),
        disambiguation=list(payload.get("disambiguation", [])),
        process_identity=list(payload.get("process_identity", [])),
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
        if not (entry.get("prozess") == process_name and entry.get("anwendung_name") == application_name)
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
        if not (entry.get("prozess") == process_name and entry.get("anwendung_name") == application_name)
    ]
    return KnowledgeBase(
        confirmed=updated_confirmed,
        rejected=updated_rejected,
        disambiguation=knowledge_base.disambiguation,
        process_identity=knowledge_base.process_identity,
    )


def reject_link(knowledge_base: KnowledgeBase, process_name: str, application_name: str) -> KnowledgeBase:
    updated_rejected = [
        entry
        for entry in knowledge_base.rejected
        if not (entry.get("prozess") == process_name and entry.get("anwendung_name") == application_name)
    ]
    updated_rejected.append(
        {
            "prozess": process_name,
            "anwendung_name": application_name,
            "abgelehnt_am": date.today().isoformat(),
        }
    )
    updated_confirmed = [
        entry
        for entry in knowledge_base.confirmed
        if not (entry.get("prozess") == process_name and entry.get("anwendung_name") == application_name)
    ]
    return KnowledgeBase(
        confirmed=updated_confirmed,
        rejected=updated_rejected,
        disambiguation=knowledge_base.disambiguation,
        process_identity=knowledge_base.process_identity,
    )
