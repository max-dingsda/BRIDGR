import json

import pytest
import requests

from core.llm_client import LlmClientConfig, LlmClientError, OpenAICompatibleClient, _extract_json_object


class FakeResponse:
    def __init__(self, payload=None, status_code: int = 200, text: str = "") -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, responses=None, exception: Exception | None = None) -> None:
        self.responses = list(responses or [])
        self.exception = exception
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        if self.exception is not None:
            raise self.exception
        return self.responses.pop(0)


def build_client(monkeypatch: pytest.MonkeyPatch, session: FakeSession) -> OpenAICompatibleClient:
    monkeypatch.setattr("core.llm_client.requests.Session", lambda: session)
    return OpenAICompatibleClient(
        LlmClientConfig(
            base_url="https://example.test/v1",
            model="gpt-test",
            api_key_env="",
            timeout_seconds=15,
        )
    )


def test_generate_text_uses_session_request(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        responses=[FakeResponse(payload={"choices": [{"message": {"content": "Hallo"}}]})]
    )
    client = build_client(monkeypatch, session)

    result = client.generate_text("system", "user")

    assert result == "Hallo"
    assert session.calls == [
        {
            "method": "POST",
            "url": "https://example.test/v1/chat/completions",
            "headers": {"Content-Type": "application/json"},
            "json": {
                "model": "gpt-test",
                "messages": [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "user"},
                ],
            },
            "timeout": 15,
        }
    ]


def test_list_models_returns_model_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(responses=[FakeResponse(payload={"data": [{"id": "gpt-a"}, {"id": "gpt-b"}]})])
    client = build_client(monkeypatch, session)

    result = client.list_models()

    assert result == ["gpt-a", "gpt-b"]


def test_request_raises_helpful_error_for_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(responses=[FakeResponse(payload={}, status_code=401, text="unauthorized")])
    client = build_client(monkeypatch, session)

    with pytest.raises(LlmClientError, match="status 401: unauthorized"):
        client.list_models()


def test_request_raises_helpful_error_for_transport_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(exception=requests.ConnectionError("boom"))
    client = build_client(monkeypatch, session)

    with pytest.raises(LlmClientError, match="could not be reached"):
        client.list_models()


def test_request_rejects_invalid_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(responses=[FakeResponse(payload=json.JSONDecodeError("bad", "x", 0))])
    client = build_client(monkeypatch, session)

    with pytest.raises(LlmClientError, match="not valid JSON"):
        client.list_models()


def test_generate_json_extracts_json_object_from_markdown_wrapped_response(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        responses=[
            FakeResponse(
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": '```json\n{"process":"A","applications":[]}\n```'
                            }
                        }
                    ]
                }
            )
        ]
    )
    client = build_client(monkeypatch, session)

    result = client.generate_json("system", "user")

    assert result == {"process": "A", "applications": []}


def test_generate_json_retries_after_invalid_json_content(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        responses=[
            FakeResponse(
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": '{"process":"A","applications":['
                            }
                        }
                    ]
                }
            ),
            FakeResponse(
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": '{"process":"A","org_unit":"","applications":[]}'
                            }
                        }
                    ]
                }
            ),
        ]
    )
    client = build_client(monkeypatch, session)

    result = client.generate_json("system", "user", required_keys={"process", "org_unit", "applications"})

    assert result == {"process": "A", "org_unit": "", "applications": []}
    assert len(session.calls) == 2
    second_messages = session.calls[1]["json"]["messages"]
    # Retry starts fresh: no broken assistant context, just [system, user_original, user_retry]
    assert len(second_messages) == 3
    assert second_messages[0]["role"] == "system"
    assert second_messages[1]["role"] == "user"
    assert second_messages[1]["content"] == "user"
    assert second_messages[2]["role"] == "user"
    assert "Return only one valid JSON object" in second_messages[2]["content"]


def test_generate_json_retries_after_missing_required_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        responses=[
            FakeResponse(
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": '{"process":"A","applications":[]}'
                            }
                        }
                    ]
                }
            ),
            FakeResponse(
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": '{"process":"A","org_unit":"","applications":[]}'
                            }
                        }
                    ]
                }
            ),
        ]
    )
    client = build_client(monkeypatch, session)

    result = client.generate_json("system", "user", required_keys={"process", "org_unit", "applications"})

    assert result == {"process": "A", "org_unit": "", "applications": []}
    assert len(session.calls) == 2


def test_generate_json_raises_after_exhausting_repair_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        responses=[
            FakeResponse(payload={"choices": [{"message": {"content": "not json"}}]}),
            FakeResponse(payload={"choices": [{"message": {"content": "still not json"}}]}),
            FakeResponse(payload={"choices": [{"message": {"content": "again not json"}}]}),
        ]
    )
    client = build_client(monkeypatch, session)

    with pytest.raises(LlmClientError, match="not valid JSON"):
        client.generate_json("system", "user")

    assert len(session.calls) == 3


def test_generate_json_logs_requests_and_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        responses=[
            FakeResponse(
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": '{"process":"A","org_unit":"","applications":[]}'
                            }
                        }
                    ]
                }
            )
        ]
    )
    logged_events = []
    monkeypatch.setattr("core.llm_client.requests.Session", lambda: session)
    client = OpenAICompatibleClient(
        LlmClientConfig(
            base_url="https://example.test/v1",
            model="gpt-test",
            timeout_seconds=15,
            debug_logger=lambda event, details: logged_events.append((event, details)),
        )
    )

    result = client.generate_json("system", "user", required_keys={"process", "org_unit", "applications"})

    assert result == {"process": "A", "org_unit": "", "applications": []}
    assert logged_events[0][0] == "llm_request"
    assert logged_events[1][0] == "llm_response"
    assert logged_events[0][1]["messages"][0]["content"] == "system"
    assert logged_events[1][1]["content"] == '{"process":"A","org_unit":"","applications":[]}'


def test_extract_json_object_handles_nested_json_without_regex() -> None:
    extracted = _extract_json_object('prefix {"outer":{"inner":[1,2,3]}} suffix')

    assert extracted == '{"outer":{"inner":[1,2,3]}}'


# --- generate_with_tools ---

def test_generate_with_tools_returns_content_when_no_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        responses=[
            FakeResponse(payload={"choices": [{"message": {"content": "Direkte Antwort", "tool_calls": []}}]})
        ]
    )
    client = build_client(monkeypatch, session)

    content, tool_calls = client.generate_with_tools(
        [{"role": "user", "content": "Frage"}],
        [{"type": "function", "function": {"name": "execute_cypher", "parameters": {}}}],
    )

    assert content == "Direkte Antwort"
    assert tool_calls == []


def test_generate_with_tools_returns_tool_calls_from_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    tool_calls_payload = [
        {
            "id": "call_abc",
            "type": "function",
            "function": {"name": "execute_cypher", "arguments": '{"query": "MATCH (p:Process) RETURN p.name"}'},
        }
    ]
    session = FakeSession(
        responses=[
            FakeResponse(
                payload={"choices": [{"message": {"content": None, "tool_calls": tool_calls_payload}}]}
            )
        ]
    )
    client = build_client(monkeypatch, session)

    content, tool_calls = client.generate_with_tools(
        [{"role": "user", "content": "Frage"}],
        [{"type": "function", "function": {"name": "execute_cypher", "parameters": {}}}],
    )

    assert content == ""
    assert len(tool_calls) == 1
    assert tool_calls[0]["id"] == "call_abc"
    assert tool_calls[0]["function"]["name"] == "execute_cypher"


def test_generate_with_tools_sends_tools_in_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        responses=[
            FakeResponse(payload={"choices": [{"message": {"content": "ok", "tool_calls": None}}]})
        ]
    )
    client = build_client(monkeypatch, session)
    tools = [{"type": "function", "function": {"name": "execute_cypher"}}]

    client.generate_with_tools([{"role": "user", "content": "test"}], tools)

    sent_payload = session.calls[0]["json"]
    assert sent_payload["tools"] == tools
    assert sent_payload["tool_choice"] == "auto"


def test_generate_with_tools_raises_on_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(responses=[FakeResponse(payload={"choices": []})])
    client = build_client(monkeypatch, session)

    with pytest.raises(LlmClientError, match="chat completion message"):
        client.generate_with_tools([{"role": "user", "content": "test"}], [])
