from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests


class LlmClientError(RuntimeError):
    pass


@dataclass(slots=True)
class LlmClientConfig:
    base_url: str
    model: str
    api_key_env: str = ""
    timeout_seconds: int = 60


class OpenAICompatibleClient:
    def __init__(self, config: LlmClientConfig) -> None:
        self._config = config
        self._session = requests.Session()

    def list_models(self) -> list[str]:
        payload = self._request("GET", "/models")
        models = payload.get("data", [])
        return [model["id"] for model in models if "id" in model]

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        content = self._generate_content(system_prompt, user_prompt, {"type": "json_object"})
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            extracted_content = _extract_json_object(content)
            if extracted_content is None:
                raise LlmClientError("LLM response content was not valid JSON.") from exc
            try:
                return json.loads(extracted_content)
            except json.JSONDecodeError as nested_exc:
                raise LlmClientError("LLM response content was not valid JSON.") from nested_exc

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        return self._generate_content(system_prompt, user_prompt)

    def _generate_content(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if response_format is not None:
            payload["response_format"] = response_format
        response = self._request("POST", "/chat/completions", payload)
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmClientError("LLM response did not contain a chat completion message.") from exc

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        base_url = self._config.base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}

        api_key = self._resolve_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = self._session.request(
                method=method,
                url=f"{base_url}{path}",
                headers=headers,
                json=payload,
                timeout=self._config.timeout_seconds,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            response_body = exc.response.text if exc.response is not None else str(exc)
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            raise LlmClientError(f"LLM request failed with status {status_code}: {response_body}") from exc
        except requests.RequestException as exc:
            raise LlmClientError(f"LLM endpoint could not be reached: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise LlmClientError("LLM response was not valid JSON.") from exc

    def _resolve_api_key(self) -> str:
        if not self._config.api_key_env:
            return ""
        return os.getenv(self._config.api_key_env, "")


def _extract_json_object(content: str) -> str | None:
    start_index = None
    brace_depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(content):
        if start_index is None:
            if char == "{":
                start_index = index
                brace_depth = 1
            continue

        if in_string:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            brace_depth += 1
            continue
        if char == "}":
            brace_depth -= 1
            if brace_depth == 0:
                return content[start_index : index + 1]

    return None
