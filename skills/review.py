from __future__ import annotations

from dataclasses import dataclass

from core.constants import CONFIDENCE_WEAK, MATCH_SOURCE_REJECTED
from skills.extract.extract_base import ExtractedProcess
from skills.match import MatchResult


@dataclass(slots=True)
class ReviewItem:
    process_name: str
    application_name: str
    reason: str


def collect_review_items(process: ExtractedProcess, matches: list[MatchResult]) -> list[ReviewItem]:
    strongly_matched_apps = {
        match.application_name
        for match in matches
        if match.confidence != CONFIDENCE_WEAK
        and match.cmdb_id is not None
        and match.source != MATCH_SOURCE_REJECTED
    }
    review_items: list[ReviewItem] = []
    for match in matches:
        if match.source == MATCH_SOURCE_REJECTED:
            continue
        if match.application_name in strongly_matched_apps:
            continue
        if match.confidence == CONFIDENCE_WEAK or match.cmdb_id is None:
            review_items.append(
                ReviewItem(
                    process_name=process.process_name,
                    application_name=match.application_name,
                    reason=match.source,
                )
            )
    return review_items
