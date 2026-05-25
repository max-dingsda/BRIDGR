from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

from llm_client import OpenAICompatibleClient
from skills.extract.extract_base import ApplicationReference, ExtractedProcess


class BpmnExtractorError(RuntimeError):
    pass


class BpmnExtractor:
    def __init__(self, prompt_path: Path, llm_client: OpenAICompatibleClient) -> None:
        self._prompt_path = prompt_path
        self._llm_client = llm_client

    def extract(self, source_path: Path) -> ExtractedProcess:
        bpmn_xml = source_path.read_text(encoding="utf-8")
        self._validate_xml(bpmn_xml, source_path)
        prompt = self._prompt_path.read_text(encoding="utf-8")
        payload = self._llm_client.generate_json(
            system_prompt=prompt,
            user_prompt=bpmn_xml,
        )
        return self._to_domain_model(payload, source_path)

    def _validate_xml(self, xml_text: str, source_path: Path) -> None:
        try:
            ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            raise BpmnExtractorError(f"Invalid BPMN XML in {source_path}.") from exc

    def _to_domain_model(self, payload: dict, source_path: Path) -> ExtractedProcess:
        try:
            applications = [
                ApplicationReference(
                    name=item["name"],
                    confidence=item["konfidenz"],
                )
                for item in payload["anwendungen"]
            ]
            return ExtractedProcess(
                process_name=payload["prozess"],
                process_id=payload["prozess_id"],
                org_unit=payload["org_einheit"],
                follows_after=list(payload.get("folgt_auf", [])),
                applications=applications,
                source_path=str(source_path),
            )
        except (KeyError, TypeError) as exc:
            serialized_payload = json.dumps(payload, ensure_ascii=False)
            raise BpmnExtractorError(f"LLM extraction payload did not match the expected schema: {serialized_payload}") from exc

