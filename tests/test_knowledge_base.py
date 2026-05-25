import json
from pathlib import Path

import pytest

from knowledge_base import KnowledgeBase, clear_knowledge_base_sections, confirm_link, reject_link
from knowledge_base import load_knowledge_base


def test_confirm_link_adds_confirmed_entry_and_removes_rejection() -> None:
    knowledge_base = KnowledgeBase(
        confirmed=[],
        rejected=[{"prozess": "Auftragsabwicklung", "anwendung_name": "SAP Sales", "abgelehnt_am": "2026-05-25"}],
        disambiguation=[],
        process_identity=[],
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
    )

    cleared = clear_knowledge_base_sections(knowledge_base, {"confirmed", "rejected"})

    assert cleared.confirmed == []
    assert cleared.rejected == []
    assert cleared.disambiguation == [{"name": "Adobe"}]
    assert cleared.process_identity == [{"name_a": "A", "name_b": "B"}]
