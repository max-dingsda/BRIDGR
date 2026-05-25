from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(slots=True)
class MatchResult:
    application_name: str
    cmdb_id: str | None
    matched_name: str | None
    confidence: str
    source: str


def match_application(
    application_name: str,
    process_name: str,
    cmdb_rows: list[dict[str, str]],
    confirmed_links: list[dict[str, str]],
    rejected_links: list[dict[str, str]],
    threshold: float,
    uuid_column: str,
    name_column: str,
) -> MatchResult:
    for link in confirmed_links:
        if link.get("prozess") == process_name and link.get("anwendung_name") == application_name:
            return MatchResult(
                application_name=application_name,
                cmdb_id=link.get("cmdb_id"),
                matched_name=link.get("resolved_to", application_name),
                confidence="stark",
                source="knowledge_base",
            )

    for link in rejected_links:
        if link.get("prozess") == process_name and link.get("anwendung_name") == application_name:
            return MatchResult(
                application_name=application_name,
                cmdb_id=None,
                matched_name=None,
                confidence="schwach",
                source="rejected",
            )

    best_row = None
    best_score = 0.0
    for row in cmdb_rows:
        candidate_name = row.get(name_column, "")
        score = SequenceMatcher(None, application_name.lower(), candidate_name.lower()).ratio()
        if score > best_score:
            best_score = score
            best_row = row

    if best_row and best_score >= threshold:
        return MatchResult(
            application_name=application_name,
            cmdb_id=best_row.get(uuid_column),
            matched_name=best_row.get(name_column),
            confidence="stark" if best_score >= 0.95 else "schwach",
            source="fuzzy",
        )

    return MatchResult(
        application_name=application_name,
        cmdb_id=None,
        matched_name=None,
        confidence="schwach",
        source="unmatched",
    )
