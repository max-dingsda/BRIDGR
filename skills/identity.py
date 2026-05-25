from __future__ import annotations

from xml.etree import ElementTree


def extract_bpmn_process_ids(xml_text: str) -> list[str]:
    root = ElementTree.fromstring(xml_text)
    process_ids: list[str] = []
    for element in root.iter():
        if element.tag.endswith("process"):
            process_id = element.attrib.get("id")
            if process_id:
                process_ids.append(process_id)
    return process_ids

