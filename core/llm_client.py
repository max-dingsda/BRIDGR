from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

import requests


class LlmClientError(RuntimeError):
    pass


@dataclass(slots=True)
class LlmClientConfig:
    base_url: str
    model: str
    api_key_env: str = ""
    timeout_seconds: int = 300
    json_temperature: float = 0.1
    debug_logger: Callable[[str, dict[str, Any]], None] | None = None


class OpenAICompatibleClient:
    _JSON_REPAIR_MAX_ATTEMPTS = 3

    def __init__(self, config: LlmClientConfig) -> None:
        self._config = config
        self._session = requests.Session()

    def list_models(self) -> list[str]:
        payload = self._request("GET", "/models")
        models = payload.get("data", [])
        return [model["id"] for model in models if "id" in model]

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        required_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        original_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        messages = list(original_messages)
        last_error_message = "LLM response content was not valid JSON."

        for attempt_index in range(self._JSON_REPAIR_MAX_ATTEMPTS):
            self._log_debug(
                "llm_request",
                {
                    "attempt": attempt_index + 1,
                    "model": self._config.model,
                    "response_format": {"type": "json_object"},
                    "messages": messages,
                },
            )
            content = self._generate_content_from_messages(
                messages,
                {"type": "json_object"},
                temperature=self._config.json_temperature,
            )
            self._log_debug(
                "llm_response",
                {
                    "attempt": attempt_index + 1,
                    "model": self._config.model,
                    "content": content,
                },
            )
            try:
                payload = _parse_json_content(content)
                self._validate_required_keys(payload, required_keys)
                return payload
            except LlmClientError as exc:
                last_error_message = str(exc)
                self._log_debug(
                    "llm_response_invalid",
                    {
                        "attempt": attempt_index + 1,
                        "model": self._config.model,
                        "error": last_error_message,
                        "content": content,
                    },
                )
                if attempt_index == self._JSON_REPAIR_MAX_ATTEMPTS - 1:
                    raise
                # Start fresh — don't carry degenerate output back as assistant context,
                # since feeding broken JSON back conditions the model to repeat the failure.
                messages = list(original_messages) + [
                    {
                        "role": "user",
                        "content": self._build_json_repair_instruction(required_keys, last_error_message),
                    }
                ]

        raise LlmClientError(last_error_message)

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        self._log_debug(
            "llm_request",
            {
                "attempt": 1,
                "model": self._config.model,
                "response_format": None,
                "messages": messages,
            },
        )
        content = self._generate_content_from_messages(messages)
        self._log_debug(
            "llm_response",
            {
                "attempt": 1,
                "model": self._config.model,
                "content": content,
            },
        )
        return content

    def generate_chat(self, messages: list[dict[str, str]]) -> str:
        self._log_debug(
            "llm_request",
            {
                "attempt": 1,
                "model": self._config.model,
                "response_format": None,
                "messages": messages,
            },
        )
        content = self._generate_content_from_messages(messages)
        self._log_debug(
            "llm_response",
            {
                "attempt": 1,
                "model": self._config.model,
                "content": content,
            },
        )
        return content

    def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        self._log_debug(
            "llm_request",
            {
                "attempt": 1,
                "model": self._config.model,
                "response_format": None,
                "messages": messages,
                "tools": tools,
            },
        )
        response = self._request("POST", "/chat/completions", payload)
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmClientError("LLM response did not contain a chat completion message.") from exc
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []
        self._log_debug(
            "llm_response",
            {
                "attempt": 1,
                "model": self._config.model,
                "content": content,
                "tool_calls": tool_calls,
            },
        )
        return content, tool_calls

    def _generate_content(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._generate_content_from_messages(messages, response_format)

    def _generate_content_from_messages(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> str:
        payload = {
            "model": self._config.model,
            "messages": messages,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if temperature is not None:
            payload["temperature"] = temperature
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

    def _log_debug(self, event: str, details: dict[str, Any]) -> None:
        if self._config.debug_logger is None:
            return
        try:
            self._config.debug_logger(event, details)
        except Exception:
            return

    def _validate_required_keys(self, payload: dict[str, Any], required_keys: set[str] | None) -> None:
        if required_keys is None:
            return
        missing_keys = sorted(key for key in required_keys if key not in payload)
        if missing_keys:
            raise LlmClientError(
                "LLM JSON response was missing required keys: " + ", ".join(missing_keys)
            )

    def _build_json_repair_instruction(self, required_keys: set[str] | None, error_message: str) -> str:
        required_keys_text = ""
        if required_keys:
            required_keys_text = (
                " The JSON object must include these top-level keys: "
                + ", ".join(sorted(required_keys))
                + "."
            )
        return (
            "Return only one valid JSON object with no Markdown, no explanation, and no surrounding text. "
            "Ensure all brackets and braces are properly closed and all strings are properly terminated."
            f"{required_keys_text}"
        )


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


def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        extracted_content = _extract_json_object(content)
        if extracted_content is None:
            raise LlmClientError("LLM response content was not valid JSON.") from exc
        try:
            payload = json.loads(extracted_content)
        except json.JSONDecodeError as nested_exc:
            raise LlmClientError("LLM response content was not valid JSON.") from nested_exc

    if not isinstance(payload, dict):
        raise LlmClientError("LLM JSON response was not an object.")
    return payload


__all__ = [
    "LlmClientConfig",
    "LlmClientError",
    "OpenAICompatibleClient",
    "_extract_json_object",
    "_parse_json_content",
    "generate_chat",
]
