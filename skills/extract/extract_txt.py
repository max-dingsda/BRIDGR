from __future__ import annotations

import json
from pathlib import Path

from llm_client import OpenAICompatibleClient
from skills.extract.extract_base import ApplicationReference, ExtractedProcess
from skills.extract.extract_bpmn import BpmnExtractor


class TextExtractorError(RuntimeError):
    pass


class TextExtractor:
    def __init__(self, prompt_path: Path, llm_client: OpenAICompatibleClient) -> None:
        self._prompt_path = prompt_path
        self._llm_client = llm_client
        self._bpmn_normalizer = BpmnExtractor(prompt_path=prompt_path, llm_client=llm_client)

    def extract(self, source_path: Path) -> ExtractedProcess:
        document_text = self._read_document_text(source_path)
        prompt = self._prompt_path.read_text(encoding="utf-8")
        payload = self._llm_client.generate_json(
            system_prompt=prompt,
            user_prompt=document_text,
        )
        return self._to_domain_model(payload, source_path)

    def _read_document_text(self, source_path: Path) -> str:
        try:
            return source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise TextExtractorError(f"Text document in {source_path} is not valid UTF-8.") from exc

    def _to_domain_model(self, payload: dict, source_path: Path) -> ExtractedProcess:
        try:
            raw_applications = [
                ApplicationReference(
                    name=item["name"],
                    confidence=item["konfidenz"],
                )
                for item in payload["anwendungen"]
            ]
            applications = self._bpmn_normalizer._deduplicate_applications(payload["anwendungen"])
            process_id = str(payload.get("prozess_id") or source_path.stem)
            return ExtractedProcess(
                process_name=payload["prozess"],
                process_id=process_id,
                org_unit=payload["org_einheit"],
                follows_after=list(payload.get("folgt_auf", [])),
                raw_applications=raw_applications,
                applications=applications,
                source_path=str(source_path),
            )
        except (KeyError, TypeError) as exc:
            serialized_payload = json.dumps(payload, ensure_ascii=False)
            raise TextExtractorError(
                f"LLM extraction payload did not match the expected schema: {serialized_payload}"
            ) from exc
