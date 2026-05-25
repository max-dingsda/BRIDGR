from knowledge_base import KnowledgeBase, confirm_link, reject_link


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
