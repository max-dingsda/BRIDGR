from pathlib import Path

import pytest

from bpmn_transformer import BpmnTransformError, transform_bpmn_for_import


def test_transform_bpmn_for_import_writes_compact_text_file(tmp_path: Path) -> None:
    source_path = tmp_path / "sample.bpmn"
    source_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" name="Sample">
  <collaboration id="collab_1">
    <participant id="participant_1" name="Trouble Ticket System" processRef="proc_1" />
  </collaboration>
  <process id="proc_1" name="Incident Management">
    <laneSet id="lane_set_1">
      <lane id="lane_1" name="1st level support" />
      <lane id="lane_2" name="2nd level support" />
    </laneSet>
    <serviceTask id="task_1" name="Mail Interface" />
  </process>
</definitions>
""",
        encoding="utf-8",
    )

    transformed_paths = transform_bpmn_for_import(source_path, tmp_path)

    assert transformed_paths == [tmp_path / "transformed" / "sample__Incident_Management__bridgr_transform.txt"]
    transformed_text = transformed_paths[0].read_text(encoding="utf-8")
    assert "Process Name: Incident Management" in transformed_text
    assert "Lane Labels: 1st level support, 2nd level support" in transformed_text
    assert "Applications: Mail Interface, Trouble Ticket System" in transformed_text
    assert "Overall Applications:" not in transformed_text


def test_transform_bpmn_for_import_keeps_participants_process_local_and_skips_generic_names(tmp_path: Path) -> None:
    source_path = tmp_path / "sample_multi.bpmn"
    source_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" name="Sample">
  <collaboration id="collab_1">
    <participant id="participant_1" name="SAP Ticket System" processRef="proc_1" />
    <participant id="participant_2" name="Participant" processRef="proc_1" />
    <participant id="participant_3" name="Participant 2" processRef="proc_1" />
    <participant id="participant_4" name="Kündigungsprozess Bpanda Cloud durchführen" processRef="proc_2" />
  </collaboration>
  <process id="proc_1" name="Zugangsrechte erteilen">
    <laneSet id="lane_set_1">
      <lane id="lane_1" name="Systemadministration" />
    </laneSet>
  </process>
  <process id="proc_2" name="Kündigungsprozess">
    <serviceTask id="task_1" name="Bpanda Cloud" />
  </process>
</definitions>
""",
        encoding="utf-8",
    )

    transformed_paths = transform_bpmn_for_import(source_path, tmp_path)

    assert len(transformed_paths) == 2
    first_process_text = transformed_paths[0].read_text(encoding="utf-8")
    second_process_text = transformed_paths[1].read_text(encoding="utf-8")
    assert "Process Name: Zugangsrechte erteilen" in first_process_text
    assert "Applications: SAP Ticket System" in first_process_text
    assert "Participant," not in first_process_text
    assert "Participant 2" not in first_process_text
    assert "Kündigungsprozess Bpanda Cloud durchführen" not in first_process_text
    assert "Process Name: Kündigungsprozess" in second_process_text
    assert "Applications: Bpanda Cloud, Kündigungsprozess Bpanda Cloud durchführen" in second_process_text


def test_transform_bpmn_for_import_detects_modeled_datastore_applications(tmp_path: Path) -> None:
    source_path = tmp_path / "sample_datastore.bpmn"
    source_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" name="Sample">
  <process id="proc_1" name="Veröffentlichung zur Verfügung stellen">
    <laneSet id="lane_set_1">
      <lane id="lane_1" name="Marketing Manager" />
    </laneSet>
    <dataStoreReference id="store_1" name="Salesforce" dataStoreRef="store_ref_1" />
  </process>
</definitions>
""",
        encoding="utf-8",
    )

    transformed_paths = transform_bpmn_for_import(source_path, tmp_path)

    transformed_text = transformed_paths[0].read_text(encoding="utf-8")
    assert "Process Name: Veröffentlichung zur Verfügung stellen" in transformed_text
    assert "Lane Labels: Marketing Manager" in transformed_text
    assert "Applications: Salesforce" in transformed_text


def test_transform_bpmn_for_import_rejects_invalid_xml(tmp_path: Path) -> None:
    source_path = tmp_path / "broken.bpmn"
    source_path.write_text("<definitions>", encoding="utf-8")

    with pytest.raises(BpmnTransformError):
        transform_bpmn_for_import(source_path, tmp_path)
