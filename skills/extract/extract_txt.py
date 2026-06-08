from __future__ import annotations

import json
import inspect
from pathlib import Path
import re

from core.llm_client import OpenAICompatibleClient
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
        payload = self._generate_json_with_required_keys(
            system_prompt=prompt,
            user_prompt=document_text,
            required_keys={"prozess", "rolle", "prozess_eigentuemer", "org_einheit_kandidaten", "anwendungen"},
        )
        return self._to_domain_model(payload, source_path, document_text)

    def _read_document_text(self, source_path: Path) -> str:
        try:
            return source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise TextExtractorError(f"Text document in {source_path} is not valid UTF-8.") from exc

    def _to_domain_model(self, payload: dict, source_path: Path, document_text: str) -> ExtractedProcess:
        try:
            raw_applications = [
                ApplicationReference(
                    name=item["name"],
                    confidence=item["konfidenz"],
                )
                for item in payload["anwendungen"]
            ]
            applications = self._bpmn_normalizer._deduplicate_applications(payload["anwendungen"])
            process_id = self._resolve_process_id(payload, source_path, document_text)
            roles = self._resolve_roles(payload, document_text)
            org_unit_candidates = self._resolve_org_unit_candidates(payload, document_text)
            process_owner_candidate = self._resolve_process_owner_candidate(payload, document_text)
            return ExtractedProcess(
                process_name=payload["prozess"],
                process_id=process_id,
                org_unit="",
                roles=roles,
                org_units=[],
                org_unit_candidates=org_unit_candidates,
                follows_after=list(payload.get("folgt_auf", [])),
                raw_applications=raw_applications,
                applications=applications,
                source_path=str(source_path),
                process_owner_candidate=process_owner_candidate,
            )
        except (KeyError, TypeError) as exc:
            serialized_payload = json.dumps(payload, ensure_ascii=False)
            raise TextExtractorError(
                f"LLM extraction payload did not match the expected schema: {serialized_payload}"
            ) from exc

    def _resolve_process_id(self, payload: dict, source_path: Path, document_text: str) -> str:
        source_process_id = self._extract_process_id_from_document_text(document_text)
        if source_process_id:
            return source_process_id
        return str(payload.get("prozess_id") or source_path.stem)

    def _extract_process_id_from_document_text(self, document_text: str) -> str:
        match = re.search(r"(?mi)^\s*Process ID:\s*(\S+)\s*$", document_text)
        if not match:
            return ""
        return match.group(1).strip()

    def _resolve_roles(self, payload: dict, document_text: str) -> list[str]:
        lane_roles = self._extract_lane_labels_from_transform(document_text)
        if lane_roles:
            return lane_roles
        if self._is_bpmn_transform_text(document_text):
            return []

        role_value = str(payload.get("rolle") or payload.get("org_einheit") or "").strip()
        if not role_value:
            return []
        return [role_value]

    def _resolve_process_owner_candidate(self, payload: dict, document_text: str) -> str:
        if self._is_bpmn_transform_text(document_text):
            return ""
        raw = str(payload.get("prozess_eigentuemer") or "").strip()
        return " ".join(raw.split()) if raw else ""

    def _resolve_org_unit_candidates(self, payload: dict, document_text: str) -> list[str]:
        if self._is_bpmn_transform_text(document_text):
            return []

        raw_candidates = payload.get("org_einheit_kandidaten", [])
        if not isinstance(raw_candidates, list):
            return []

        candidates: list[str] = []
        seen: set[str] = set()
        for item in raw_candidates:
            cleaned_item = " ".join(str(item).strip().split())
            if not cleaned_item:
                continue
            normalized_item = cleaned_item.casefold()
            if normalized_item in seen:
                continue
            seen.add(normalized_item)
            candidates.append(cleaned_item)
        return candidates

    def _extract_lane_labels_from_transform(self, document_text: str) -> list[str]:
        if not self._is_bpmn_transform_text(document_text):
            return []
        match = re.search(r"(?mi)^\s*Lane Labels:\s*(.+?)\s*$", document_text)
        if not match:
            return []
        lane_labels = []
        seen: set[str] = set()
        for part in match.group(1).split(","):
            cleaned_part = " ".join(part.strip().split())
            if not cleaned_part or cleaned_part.casefold() == "none":
                continue
            normalized_part = cleaned_part.casefold()
            if normalized_part in seen:
                continue
            seen.add(normalized_part)
            lane_labels.append(cleaned_part)
        return lane_labels

    def _is_bpmn_transform_text(self, document_text: str) -> bool:
        return document_text.lstrip().startswith("BRIDGR BPMN Transform")

    def _generate_json_with_required_keys(
        self,
        system_prompt: str,
        user_prompt: str,
        required_keys: set[str],
    ) -> dict:
        generate_json = self._llm_client.generate_json
        if "required_keys" in inspect.signature(generate_json).parameters:
            return generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                required_keys=required_keys,
            )
        return generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
