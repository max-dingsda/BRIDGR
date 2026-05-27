import json
from pathlib import Path

import pytest

from knowledge_base import (
    KnowledgeBase,
    accept_org_unit_candidate_as_new,
    clear_knowledge_base_sections,
    confirm_link,
    load_knowledge_base,
    map_org_unit_candidate,
    reject_link,
    upsert_org_unit_candidate,
)


def test_confirm_link_adds_confirmed_entry_and_removes_rejection() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[{"prozess": "Auftragsabwicklung", "anwendung_name": "SAP Sales", "abgelehnt_am": "2026-05-25"}],
        disambiguation=[],
        process_identity=[],
        org_units=[],
        org_unit_candidates=[],
    )

    updated = confirm_link(
        knowledge_base,
        process_name="Auftragsabwicklung",
        application_name="SAP Sales",
        cmdb_id="cmdb-1",
        matched_name="SAP Sales",
    )

    assert len(updated.confirmed) == 1
    assert updated.confirmed[0]["cmdb_id"] == "cmdb-1"
    assert updated.rejected == []


def test_reject_link_adds_rejected_entry_and_removes_confirmation() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[{"prozess": "Auftragsabwicklung", "anwendung_name": "SAP Sales", "cmdb_id": "cmdb-1"}],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[],
        org_unit_candidates=[],
    )

    updated = reject_link(
        knowledge_base,
        process_name="Auftragsabwicklung",
        application_name="SAP Sales",
    )

    assert updated.confirmed == []
    assert len(updated.rejected) == 1
    assert updated.rejected[0]["anwendung_name"] == "SAP Sales"


def test_confirm_link_allows_multiple_confirmed_targets_for_one_application() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[{"prozess": "Auftragsabwicklung", "anwendung_name": "Adobe", "cmdb_id": "cmdb-1"}],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[],
        org_unit_candidates=[],
    )

    updated = confirm_link(
        knowledge_base,
        process_name="Auftragsabwicklung",
        application_name="Adobe",
        cmdb_id="cmdb-2",
        matched_name="Adobe Professional",
    )

    assert len(updated.confirmed) == 2


def test_reject_link_can_reject_single_candidate_without_removing_other_confirmations() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[
            {"prozess": "Auftragsabwicklung", "anwendung_name": "Adobe", "cmdb_id": "cmdb-1"},
            {"prozess": "Auftragsabwicklung", "anwendung_name": "Adobe", "cmdb_id": "cmdb-2"},
        ],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[],
        org_unit_candidates=[],
    )

    updated = reject_link(
        knowledge_base,
        process_name="Auftragsabwicklung",
        application_name="Adobe",
        cmdb_id="cmdb-1",
    )

    assert len(updated.confirmed) == 1
    assert updated.confirmed[0]["cmdb_id"] == "cmdb-2"
    assert updated.rejected[0]["cmdb_id"] == "cmdb-1"


def test_load_knowledge_base_raises_for_corrupt_json(tmp_path: Path) -> None:
    kb_path = tmp_path / "kb.json"
    kb_path.write_text("{broken", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_knowledge_base(kb_path)


def test_clear_knowledge_base_sections_resets_only_selected_parts() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[{"prozess": "A", "anwendung_name": "App", "cmdb_id": "1", "resolved_to": "App", "bestaetigt_am": "2026-05-25", "quelle": "manuell"}],
        rejected=[{"prozess": "A", "anwendung_name": "App", "cmdb_id": "1", "abgelehnt_am": "2026-05-25"}],
        disambiguation=[{"name": "Adobe"}],
        process_identity=[{"name_a": "A", "name_b": "B"}],
        org_units=[{"name": "IT", "created_at": "2026-05-27", "source": "manual"}],
        org_unit_candidates=[{"candidate_name": "Marketing", "normalized_name": "marketing", "source_paths": ["a.txt"], "process_names": ["A"], "role_names": ["Leitung"], "status": "open", "mapped_org_unit": "", "first_seen": "2026-05-27", "last_seen": "2026-05-27"}],
    )

    cleared = clear_knowledge_base_sections(knowledge_base, {"confirmed", "rejected"})

    assert cleared.confirmed == []
    assert cleared.rejected == []
    assert cleared.disambiguation == [{"name": "Adobe"}]
    assert cleared.process_identity == [{"name_a": "A", "name_b": "B"}]
    assert cleared.org_units == [{"name": "IT", "created_at": "2026-05-27", "source": "manual"}]
    assert cleared.org_unit_candidates[0]["candidate_name"] == "Marketing"


def test_upsert_org_unit_candidate_merges_duplicate_observations() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[],
        org_unit_candidates=[],
    )

    updated = upsert_org_unit_candidate(knowledge_base, "Marketing", "a.txt", "P1", "Lead")
    updated = upsert_org_unit_candidate(updated, "marketing", "b.txt", "P2", "Manager")

    assert len(updated.org_unit_candidates) == 1
    assert updated.org_unit_candidates[0]["source_paths"] == ["a.txt", "b.txt"]
    assert updated.org_unit_candidates[0]["process_names"] == ["P1", "P2"]
    assert updated.org_unit_candidates[0]["role_names"] == ["Lead", "Manager"]


def test_map_and_accept_org_unit_candidate_promote_candidate() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[],
        disambiguation=[],
        process_identity=[],
        org_units=[],
        org_unit_candidates=[],
    )

    updated = upsert_org_unit_candidate(knowledge_base, "People & Culture", "a.txt", "P1", "HR")
    mapped = accept_org_unit_candidate_as_new(updated, "People & Culture")
    remapped = map_org_unit_candidate(mapped, "People & Culture", "People & Culture")

    assert remapped.org_units[0]["name"] == "People & Culture"
    assert remapped.org_unit_candidates[0]["status"] == "mapped"
    assert remapped.org_unit_candidates[0]["mapped_org_unit"] == "People & Culture"
