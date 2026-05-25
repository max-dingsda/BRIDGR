from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from constants import (
    CONFIDENCE_STRONG,
    CONFIDENCE_WEAK,
    MATCH_SOURCE_FUZZY,
    MATCH_SOURCE_KNOWLEDGE_BASE,
    MATCH_SOURCE_REJECTED,
    MATCH_SOURCE_UNMATCHED,
)
from knowledge_base import ConfirmedLink, RejectedLink


@dataclass(slots=True)
class MatchResult:
    application_name: str
    cmdb_id: str | None
    matched_name: str | None
    confidence: str
    source: str
    score: float = 0.0


def match_application(
    application_name: str,
    process_name: str,
    cmdb_rows: list[dict[str, str]],
    confirmed_links: list[ConfirmedLink],
    rejected_links: list[RejectedLink],
    threshold: float,
    uuid_column: str,
    name_column: str,
) -> MatchResult:
    candidates = match_application_candidates(
        application_name=application_name,
        process_name=process_name,
        cmdb_rows=cmdb_rows,
        confirmed_links=confirmed_links,
        rejected_links=rejected_links,
        threshold=threshold,
        uuid_column=uuid_column,
        name_column=name_column,
    )
    return candidates[0]


def match_application_candidates(
    application_name: str,
    process_name: str,
    cmdb_rows: list[dict[str, str]],
    confirmed_links: list[ConfirmedLink],
    rejected_links: list[RejectedLink],
    threshold: float,
    uuid_column: str,
    name_column: str,
) -> list[MatchResult]:
    confirmed_matches = [
        MatchResult(
            application_name=application_name,
            cmdb_id=link.get("cmdb_id"),
            matched_name=link.get("resolved_to", application_name),
            confidence=CONFIDENCE_STRONG,
            source=MATCH_SOURCE_KNOWLEDGE_BASE,
            score=1.0,
        )
        for link in confirmed_links
        if link.get("prozess") == process_name and link.get("anwendung_name") == application_name
    ]
    if confirmed_matches:
        return confirmed_matches

    if is_application_rejected(process_name, application_name, rejected_links):
        return [
            MatchResult(
                application_name=application_name,
                cmdb_id=None,
                matched_name=None,
                confidence=CONFIDENCE_WEAK,
                source=MATCH_SOURCE_REJECTED,
            )
        ]

    candidate_matches = build_fuzzy_candidates(
        application_name=application_name,
        process_name=process_name,
        cmdb_rows=cmdb_rows,
        rejected_links=rejected_links,
        threshold=threshold,
        uuid_column=uuid_column,
        name_column=name_column,
    )
    if candidate_matches:
        return candidate_matches

    return [
        MatchResult(
            application_name=application_name,
            cmdb_id=None,
            matched_name=None,
            confidence=CONFIDENCE_WEAK,
            source=MATCH_SOURCE_UNMATCHED,
        )
    ]


def build_fuzzy_candidates(
    application_name: str,
    process_name: str,
    cmdb_rows: list[dict[str, str]],
    rejected_links: list[RejectedLink],
    threshold: float,
    uuid_column: str,
    name_column: str,
) -> list[MatchResult]:
    candidates: list[MatchResult] = []
    normalized_application_name = normalize_name_for_matching(application_name)
    for row in cmdb_rows:
        cmdb_id = row.get(uuid_column)
        if is_candidate_rejected(process_name, application_name, cmdb_id, rejected_links):
            continue
        candidate_name = row.get(name_column, "")
        normalized_candidate_name = normalize_name_for_matching(candidate_name)
        raw_score = SequenceMatcher(None, application_name.lower(), candidate_name.lower()).ratio()
        normalized_score = SequenceMatcher(None, normalized_application_name, normalized_candidate_name).ratio()
        containment_score = compute_containment_score(normalized_application_name, normalized_candidate_name)
        score = max(raw_score, normalized_score, containment_score)
        if score < threshold:
            continue
        candidates.append(
            MatchResult(
                application_name=application_name,
                cmdb_id=cmdb_id,
                matched_name=candidate_name,
                confidence=classify_match_confidence(raw_score, normalized_score),
                source=MATCH_SOURCE_FUZZY,
                score=score,
            )
        )

    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def normalize_name_for_matching(value: str) -> str:
    without_parentheses = re.sub(r"\([^)]*\)", " ", value)
    without_package_paths = re.sub(r"\b[a-z]+:[A-Za-z0-9_.]+\b", " ", without_parentheses)
    expanded_camel_case = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", without_package_paths)
    normalized_whitespace = re.sub(r"[_./-]+", " ", expanded_camel_case)
    lowered = normalized_whitespace.lower()
    tokens = re.findall(r"[a-z0-9]+", lowered)
    filtered_tokens = [
        token
        for token in tokens
        if token
        not in {
            "interface",
            "system",
            "operation",
            "op",
            "java",
            "com",
            "camunda",
            "examples",
            "incidentmanagement",
        }
    ]
    return " ".join(filtered_tokens)


def classify_match_confidence(raw_score: float, normalized_score: float) -> str:
    if raw_score >= 0.95:
        return CONFIDENCE_STRONG
    if raw_score >= 0.85 and normalized_score >= 0.95:
        return CONFIDENCE_STRONG
    return CONFIDENCE_WEAK


def compute_containment_score(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    if left_tokens.issubset(right_tokens) or right_tokens.issubset(left_tokens):
        return 0.9
    return 0.0


def is_application_rejected(
    process_name: str,
    application_name: str,
    rejected_links: list[RejectedLink],
) -> bool:
    return any(
        link.get("prozess") == process_name
        and link.get("anwendung_name") == application_name
        and not link.get("cmdb_id")
        for link in rejected_links
    )


def is_candidate_rejected(
    process_name: str,
    application_name: str,
    cmdb_id: str | None,
    rejected_links: list[RejectedLink],
) -> bool:
    return any(
        link.get("prozess") == process_name
        and link.get("anwendung_name") == application_name
        and link.get("cmdb_id") == cmdb_id
        for link in rejected_links
    )
