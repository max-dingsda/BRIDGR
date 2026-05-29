from skills.extract.extract_base import ApplicationReference, ExtractedProcess
from skills.match import MatchResult
from skills.review import ReviewItem, collect_review_items


def _make_process() -> ExtractedProcess:
    return ExtractedProcess(
        process_name="Auftragsabwicklung",
        process_id="proc-1",
        org_unit="Vertrieb",
        roles=["Vertrieb"],
        org_units=["Vertrieb"],
        org_unit_candidates=[],
        follows_after=[],
        raw_applications=[],
        applications=[],
        source_path="Input/process.bpmn",
    )


def test_collect_review_items_includes_weak_match() -> None:
    process = _make_process()
    matches = [
        MatchResult(
            application_name="SAP Sales",
            cmdb_id="cmdb-1",
            matched_name="SAP Sales",
            confidence="schwach",
            source="fuzzy",
        )
    ]

    items = collect_review_items(process, matches)

    assert len(items) == 1
    assert items[0].application_name == "SAP Sales"
    assert items[0].process_name == "Auftragsabwicklung"


def test_collect_review_items_includes_unmatched_application() -> None:
    process = _make_process()
    matches = [
        MatchResult(
            application_name="UnknownTool",
            cmdb_id=None,
            matched_name=None,
            confidence="schwach",
            source="no_match",
        )
    ]

    items = collect_review_items(process, matches)

    assert len(items) == 1
    assert items[0].application_name == "UnknownTool"


def test_collect_review_items_excludes_rejected_match() -> None:
    process = _make_process()
    matches = [
        MatchResult(
            application_name="SAP Sales",
            cmdb_id=None,
            matched_name=None,
            confidence="schwach",
            source="rejected",
        )
    ]

    items = collect_review_items(process, matches)

    assert items == []


def test_collect_review_items_excludes_strong_match_with_cmdb_id() -> None:
    process = _make_process()
    matches = [
        MatchResult(
            application_name="SAP SD",
            cmdb_id="cmdb-2",
            matched_name="SAP SD",
            confidence="stark",
            source="fuzzy",
        )
    ]

    items = collect_review_items(process, matches)

    assert items == []


def test_collect_review_items_returns_empty_for_no_matches() -> None:
    process = _make_process()

    items = collect_review_items(process, [])

    assert items == []


def test_collect_review_items_preserves_review_reason_from_match_source() -> None:
    process = _make_process()
    matches = [
        MatchResult(
            application_name="Ticket Tool",
            cmdb_id="cmdb-3",
            matched_name="Ticketing System",
            confidence="schwach",
            source="fuzzy",
        )
    ]

    items = collect_review_items(process, matches)

    assert items[0].reason == "fuzzy"


def test_collect_review_items_handles_mixed_match_list() -> None:
    process = _make_process()
    matches = [
        MatchResult(application_name="StrongApp", cmdb_id="cmdb-1", matched_name="StrongApp", confidence="stark", source="fuzzy"),
        MatchResult(application_name="WeakApp", cmdb_id="cmdb-2", matched_name="WeakApp", confidence="schwach", source="fuzzy"),
        MatchResult(application_name="RejectedApp", cmdb_id=None, matched_name=None, confidence="schwach", source="rejected"),
        MatchResult(application_name="UnmatchedApp", cmdb_id=None, matched_name=None, confidence="schwach", source="no_match"),
    ]

    items = collect_review_items(process, matches)

    assert len(items) == 2
    assert {item.application_name for item in items} == {"WeakApp", "UnmatchedApp"}
