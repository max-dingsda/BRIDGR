from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request


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

    def list_models(self) -> list[str]:
        payload = self._request("GET", "/models")
        models = payload.get("data", [])
        return [model["id"] for model in models if "id" in model]

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        content = self._generate_content(system_prompt, user_prompt, {"type": "json_object"})
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LlmClientError("LLM response content was not valid JSON.") from exc

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
        body = None
        headers = {"Content-Type": "application/json"}

        api_key = self._resolve_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        http_request = request.Request(
            f"{base_url}{path}",
            method=method,
            data=body,
            headers=headers,
        )

        try:
            with request.urlopen(http_request, timeout=self._config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise LlmClientError(f"LLM request failed with status {exc.code}: {response_body}") from exc
        except error.URLError as exc:
            raise LlmClientError(f"LLM endpoint could not be reached: {exc.reason}") from exc

    def _resolve_api_key(self) -> str:
        if not self._config.api_key_env:
            return ""
        return os.getenv(self._config.api_key_env, "")
