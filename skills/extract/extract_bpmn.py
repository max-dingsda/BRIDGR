from __future__ import annotations

import json
import inspect
from pathlib import Path
import re
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
        payload = self._generate_json_with_required_keys(
            system_prompt=prompt,
            user_prompt=bpmn_xml,
            required_keys={"prozess", "prozess_id", "rollen", "anwendungen"},
        )
        return self._to_domain_model(payload, source_path)

    def _validate_xml(self, xml_text: str, source_path: Path) -> None:
        try:
            ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            raise BpmnExtractorError(f"Invalid BPMN XML in {source_path}.") from exc

    def _to_domain_model(self, payload: dict, source_path: Path) -> ExtractedProcess:
        try:
            raw_applications = [
                ApplicationReference(
                    name=item["name"],
                    confidence=item["konfidenz"],
                )
                for item in payload["anwendungen"]
            ]
            applications = self._deduplicate_applications(payload["anwendungen"])
            roles = self._parse_roles(payload.get("rollen", []))
            return ExtractedProcess(
                process_name=payload["prozess"],
                process_id=payload["prozess_id"],
                org_unit="",
                roles=roles,
                org_units=[],
                org_unit_candidates=[],
                follows_after=list(payload.get("folgt_auf", [])),
                raw_applications=raw_applications,
                applications=applications,
                source_path=str(source_path),
            )
        except (KeyError, TypeError) as exc:
            serialized_payload = json.dumps(payload, ensure_ascii=False)
            raise BpmnExtractorError(f"LLM extraction payload did not match the expected schema: {serialized_payload}") from exc

    def _parse_roles(self, raw_roles: object) -> list[str]:
        if not isinstance(raw_roles, list):
            return []
        seen: set[str] = set()
        roles: list[str] = []
        for item in raw_roles:
            cleaned = " ".join(str(item).strip().split())
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            roles.append(cleaned)
        return roles

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

    def _deduplicate_applications(self, raw_applications: list[dict]) -> list[ApplicationReference]:
        grouped_applications: dict[str, dict] = {}
        for item in raw_applications:
            cleaned_name = self._clean_application_name(item["name"])
            if not self._is_modeled_application_name(cleaned_name):
                continue
            normalized_key = self._normalize_application_key(cleaned_name)
            if not normalized_key:
                continue

            candidate = {
                "name": cleaned_name,
                "konfidenz": item["konfidenz"],
            }
            existing = grouped_applications.get(normalized_key)
            if existing is None or self._is_better_application_candidate(candidate, existing):
                grouped_applications[normalized_key] = candidate

        return [
            ApplicationReference(
                name=item["name"],
                confidence=item["konfidenz"],
            )
            for item in grouped_applications.values()
        ]

    def _clean_application_name(self, value: str) -> str:
        trimmed_value = value.strip()
        without_parentheses = re.sub(r"\s*\([^)]*\)\s*$", "", trimmed_value)
        return re.sub(r"\s+", " ", without_parentheses).strip()

    def _normalize_application_key(self, value: str) -> str:
        expanded_camel_case = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
        lowered = expanded_camel_case.lower()
        tokens = re.findall(r"[a-z0-9]+", lowered)
        filtered_tokens = [
            token
            for token in tokens
            if token
            not in {
                "interface",
                "system",
                "service",
                "application",
                "participant",
                "processref",
                "participantref",
            }
        ]
        return " ".join(filtered_tokens)

    def _is_better_application_candidate(self, candidate: dict, existing: dict) -> bool:
        candidate_score = self._application_candidate_score(candidate)
        existing_score = self._application_candidate_score(existing)
        if candidate_score != existing_score:
            return candidate_score > existing_score
        return len(candidate["name"]) < len(existing["name"])

    def _is_modeled_application_name(self, value: str) -> bool:
        lowered = value.lower()
        if lowered.endswith("operation"):
            return False
        return True

    def _application_candidate_score(self, candidate: dict) -> tuple[int, int, int]:
        name = candidate["name"]
        confidence = candidate["konfidenz"]
        confidence_score = 1 if confidence == "stark" else 0
        readability_score = 1 if " " in name else 0
        technical_penalty = -1 if "." in name else 0
        return confidence_score, readability_score, technical_penalty
