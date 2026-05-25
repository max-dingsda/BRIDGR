from __future__ import annotations

"""Minimal BPMN identity helpers for v1.

This module is intentionally a stub in the current project stage. For v1, BRIDGR
derives stable process identity for BPMN inputs from the XML `process id`.
Cross-run disambiguation for non-BPMN inputs remains a later extension and is
documented in the architecture rather than implemented here.
"""

from xml.etree import ElementTree


def extract_bpmn_process_ids(xml_text: str) -> list[str]:
    """Return all BPMN process ids found in the given XML text."""

    root = ElementTree.fromstring(xml_text)
    process_ids: list[str] = []
    for element in root.iter():
        if element.tag.endswith("process"):
            process_id = element.attrib.get("id")
            if process_id:
                process_ids.append(process_id)
    return process_ids
