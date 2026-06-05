from __future__ import annotations

from pathlib import Path
import re
from xml.etree import ElementTree


class BpmnTransformError(RuntimeError):
    pass


_BPMN_NAMESPACE = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}
_APPLICATION_LIKE_TAGS = {
    "participant",
    "interface",
    "serviceTask",
    "sendTask",
    "receiveTask",
    "businessRuleTask",
    "callActivity",
    "dataStoreReference",
    "dataStore",
}
_TECHNICAL_NAME_BLACKLIST = {
    "process",
    "lane",
    "start event",
    "end event",
}
_GENERIC_PARTICIPANT_PATTERN = re.compile(r"^participant(?: \d+)?$", re.IGNORECASE)
_APPLICATION_KEYWORDS = {
    "api",
    "app",
    "application",
    "bpanda",
    "cloud",
    "crm",
    "excel",
    "interface",
    "jira",
    "microsoft",
    "outlook",
    "portal",
    "sap",
    "salesforce",
    "service",
    "sharepoint",
    "system",
    "teams",
    "ticket",
    "tool",
    "workflow",
}


def transform_bpmn_for_import(source_path: Path, target_root: Path) -> list[Path]:
    xml_text = source_path.read_text(encoding="utf-8")
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise BpmnTransformError(f"Invalid BPMN XML in {source_path}.") from exc

    process_entries = _extract_process_entries(root)
    if not process_entries:
        raise BpmnTransformError(f"No BPMN processes found in {source_path}.")

    target_dir = target_root / "transformed"
    target_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    for index, entry in enumerate(process_entries, start=1):
        target_path = target_dir / _build_transform_filename(source_path, entry, index)
        target_path.write_text(_build_process_transform_text(entry, source_path), encoding="utf-8")
        written_paths.append(target_path)
    return written_paths


def _build_process_transform_text(entry: dict[str, object], source_path: Path) -> str:
    lines = [
        "BRIDGR BPMN Transform",
        f"Source File: {source_path.name}",
        "",
        f"Process Name: {entry['process_name']}",
        f"Process ID: {entry['process_id']}",
        "Lane Labels: " + (", ".join(entry["lanes"]) if entry["lanes"] else "none"),
        "Applications: " + (", ".join(entry["applications"]) if entry["applications"] else "none"),
        "",
        "Use this file as a compact process description for BRIDGR import.",
    ]
    return "\n".join(lines).strip() + "\n"


def _extract_process_entries(root: ElementTree.Element) -> list[dict[str, object]]:
    participant_names_by_process = _extract_participant_names_by_process(root)
    entries: list[dict[str, object]] = []
    for process in root.findall(".//bpmn:process", _BPMN_NAMESPACE):
        process_id = process.get("id", "").strip()
        process_name = process.get("name", "").strip() or process_id or "Unnamed Process"
        lanes = _extract_lane_names(process)
        applications = sorted(
            _extract_application_names(process, participant_names_by_process.get(process_id, set()))
        )
        entries.append(
            {
                "process_id": process_id,
                "process_name": process_name,
                "lanes": lanes,
                "applications": applications,
            }
        )
    return entries


def _build_transform_filename(source_path: Path, entry: dict[str, object], index: int) -> str:
    process_name = str(entry["process_name"]).strip() or f"process_{index}"
    safe_process_name = _slugify_filename_component(process_name)
    return f"{source_path.stem}__{safe_process_name}__bridgr_transform.txt"


def _extract_participant_names_by_process(root: ElementTree.Element) -> dict[str, set[str]]:
    names_by_process: dict[str, set[str]] = {}
    for participant in root.findall(".//bpmn:participant", _BPMN_NAMESPACE):
        candidate_name = _normalize_candidate_name(participant.get("name", ""))
        process_ref = _normalize_process_ref(participant.get("processRef", ""))
        if not candidate_name or not process_ref or _is_generic_participant_name(candidate_name):
            continue
        names_by_process.setdefault(process_ref, set()).add(candidate_name)
    return names_by_process


def _extract_unassigned_participant_names(root: ElementTree.Element) -> set[str]:
    names: set[str] = set()
    for participant in root.findall(".//bpmn:participant", _BPMN_NAMESPACE):
        candidate_name = _normalize_candidate_name(participant.get("name", ""))
        if not candidate_name or _is_generic_participant_name(candidate_name):
            continue
        names.add(candidate_name)
    return names


def _extract_lane_names(process: ElementTree.Element) -> list[str]:
    lane_names = {
        lane_name
        for lane in process.findall(".//bpmn:lane", _BPMN_NAMESPACE)
        if (lane_name := _normalize_candidate_name(lane.get("name", "")))
    }
    return sorted(lane_names)


def _extract_application_names(process: ElementTree.Element, participant_names: set[str]) -> set[str]:
    application_names = set(participant_names)
    for element in process.iter():
        tag_name = _local_name(element.tag)
        if tag_name not in _APPLICATION_LIKE_TAGS:
            continue
        candidate_name = _normalize_candidate_name(element.get("name", ""))
        if _is_application_like(candidate_name):
            application_names.add(candidate_name)
        implementation_ref = _normalize_candidate_name(element.get("implementationRef", ""))
        if _is_application_like(implementation_ref):
            application_names.add(implementation_ref)
        operation_ref = _normalize_candidate_name(element.get("operationRef", ""))
        if _is_application_like(operation_ref):
            application_names.add(operation_ref)
    return application_names


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalize_candidate_name(value: str) -> str:
    trimmed = re.sub(r"\s+", " ", value.strip())
    if ":" in trimmed:
        trimmed = trimmed.split(":", 1)[1].strip()
    trimmed = trimmed.replace("_", " ")
    trimmed = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", trimmed)
    return trimmed.strip()


def _normalize_process_ref(value: str) -> str:
    trimmed = value.strip()
    if ":" in trimmed:
        trimmed = trimmed.split(":")[-1].strip()
    return trimmed


def _is_generic_participant_name(value: str) -> bool:
    return bool(_GENERIC_PARTICIPANT_PATTERN.fullmatch(value.strip()))


def _slugify_filename_component(value: str) -> str:
    normalized = re.sub(r"\s+", "_", value.strip())
    normalized = re.sub(r"[^A-Za-z0-9_-]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "process"


def _is_application_like(value: str) -> bool:
    if not value:
        return False
    lowered = value.casefold()
    if lowered in _TECHNICAL_NAME_BLACKLIST:
        return False
    if lowered.endswith("operation"):
        return False
    if _is_generic_participant_name(value):
        return False
    tokens = re.findall(r"[a-z0-9]+", lowered)
    if not tokens:
        return False
    return any(token in _APPLICATION_KEYWORDS for token in tokens)
