from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs

import pytest

from skiller.domain.agent.agent_llm_provider_model import AgentCodexLLMModel
from skiller.domain.agent.llm_model import LLMUserMessage
from skiller.domain.agent.llm_request import CodexLLMRequest
from skiller.infrastructure.llm.codex import codex_llm_port
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentials,
    CodexCredentialsError,
)
from skiller.infrastructure.llm.codex.codex_llm_port import (
    CODEX_BASE_URL,
    CODEX_ORIGINATOR,
    CODEX_USER_AGENT,
    CodexLLMPort,
)

pytestmark = pytest.mark.unit


class _FakeCredentialsDatasource:
    def __init__(self) -> None:
        self.credentials = _codex_credentials()
        self.credentials_file: str | None = None
        self.saved_credentials_file: str | None = None
        self.saved_token_response: dict[str, object] | None = None

    def load(self, credentials_file: str) -> CodexCredentials:
        self.credentials_file = credentials_file
        return self.credentials

    def refresh(
        self,
        credentials_file: str,
        token_response: dict[str, object],
    ) -> CodexCredentials:
        self.saved_credentials_file = credentials_file
        self.saved_token_response = token_response
        self.credentials = _codex_credentials(
            access_token=_token_with_account_id("account-2"),
            refresh_token="new-refresh-token",
            expires_in=600,
            expires_at=1600,
            id_token="new-id-token",
        )
        return self.credentials


class _BrokenCredentialsDatasource:
    def load(self, credentials_file: str) -> CodexCredentials:
        _ = credentials_file
        raise CodexCredentialsError("broken credentials")

    def refresh(
        self,
        credentials_file: str,
        token_response: dict[str, object],
    ) -> CodexCredentials:
        _ = credentials_file
        _ = token_response
        raise AssertionError("refresh should not run")


class _FakeStream:
    def __init__(
        self,
        events: list[object],
        error_after_events: Exception | None = None,
    ) -> None:
        self.events = events
        self.error_after_events = error_after_events

    def __iter__(self) -> Any:
        if self.error_after_events is None:
            return iter(self.events)

        def iterator() -> Any:
            yield from self.events
            raise self.error_after_events

        return iterator()


class _FakeResponses:
    def __init__(
        self,
        events: list[object],
        error_after_events: Exception | None = None,
    ) -> None:
        self.events = events
        self.error_after_events = error_after_events
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _FakeStream:
        self.calls.append(kwargs)
        return _FakeStream(self.events, self.error_after_events)


class _FakeOpenAI:
    instances: list["_FakeOpenAI"] = []
    events: list[object] = []
    error_after_events: Exception | None = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.responses = _FakeResponses(
            self.events,
            self.error_after_events,
        )
        self.instances.append(self)


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *args: object) -> None:
        _ = args

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_codex_llm_port_builds_client_with_codex_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.error_after_events = None
    _FakeOpenAI.events = []
    datasource = _FakeCredentialsDatasource()
    monkeypatch.setattr(
        codex_llm_port,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )

    llm = CodexLLMPort(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_datasource=datasource,
    )
    llm.generate(
        CodexLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentCodexLLMModel.GPT_5_4,
            parallel_tool_calls=True,
        )
    )

    assert datasource.credentials_file == "/tmp/openai-codex.json"
    assert _FakeOpenAI.instances[0].kwargs == {
        "api_key": _token_with_account_id("account-1"),
        "base_url": CODEX_BASE_URL,
        "timeout": 120,
        "default_headers": {
            "User-Agent": CODEX_USER_AGENT,
            "originator": CODEX_ORIGINATOR,
            "ChatGPT-Account-ID": "account-1",
        },
    }


def test_codex_llm_port_streams_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.error_after_events = None
    _FakeOpenAI.events = [
        SimpleNamespace(type="response.output_text.delta", delta="hello"),
        SimpleNamespace(type="response.output_text.delta", delta=" codex"),
    ]
    monkeypatch.setattr(
        codex_llm_port,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )
    llm = CodexLLMPort(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_datasource=_FakeCredentialsDatasource(),
    )

    response = llm.generate(
        CodexLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentCodexLLMModel.GPT_5_4,
            parallel_tool_calls=True,
        )
    )

    assert response.ok is True
    assert response.content == "hello codex"
    assert _FakeOpenAI.instances[0].responses.calls == [
        {
            "model": "gpt-5.4",
            "instructions": "",
            "input": [{"role": "user", "content": "hello"}],
            "store": False,
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "stream": True,
        }
    ]


def test_codex_llm_port_reads_completed_event_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.error_after_events = None
    _FakeOpenAI.events = [
        SimpleNamespace(type="response.output_text.delta", delta="hello"),
        SimpleNamespace(
            type="response.completed",
            response=SimpleNamespace(
                model="gpt-5.4",
                status="completed",
                output=None,
                usage=SimpleNamespace(
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                ),
            ),
        ),
    ]
    monkeypatch.setattr(
        codex_llm_port,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )
    llm = CodexLLMPort(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_datasource=_FakeCredentialsDatasource(),
    )

    response = llm.generate(
        CodexLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentCodexLLMModel.GPT_5_4,
            parallel_tool_calls=True,
        )
    )

    assert response.ok is True
    assert response.usage is not None
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5
    assert response.usage.total_tokens == 15


def test_codex_llm_port_keeps_stream_items_when_raw_stream_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool_call = SimpleNamespace(
        type="function_call",
        call_id="call-1",
        name="shell",
        arguments='{"command":"echo ok"}',
    )
    _FakeOpenAI.instances = []
    _FakeOpenAI.events = [
        SimpleNamespace(type="response.output_item.done", item=tool_call),
    ]
    _FakeOpenAI.error_after_events = TypeError("'NoneType' object is not iterable")
    monkeypatch.setattr(
        codex_llm_port,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )
    llm = CodexLLMPort(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_datasource=_FakeCredentialsDatasource(),
    )

    response = llm.generate(
        CodexLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentCodexLLMModel.GPT_5_4,
            parallel_tool_calls=True,
        )
    )

    assert response.ok is True
    assert response.model == "gpt-5.4"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "call-1"
    assert response.tool_calls[0].function.name == "shell"
    assert response.tool_calls[0].function.arguments_json == '{"command":"echo ok"}'


def test_codex_llm_port_returns_credentials_error_before_building_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    monkeypatch.setattr(
        codex_llm_port,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )
    llm = CodexLLMPort(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_datasource=_BrokenCredentialsDatasource(),
    )

    response = llm.generate(
        CodexLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentCodexLLMModel.GPT_5_4,
            parallel_tool_calls=True,
        )
    )

    assert response.ok is False
    assert response.error == "Codex credentials failed: broken credentials"
    assert response.error_code == "credentials_error"
    assert _FakeOpenAI.instances == []


def test_codex_llm_port_refreshes_expired_token_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.events = []
    _FakeOpenAI.error_after_events = None
    datasource = _FakeCredentialsDatasource()
    datasource.credentials = _codex_credentials(expires_at=1)
    monkeypatch.setattr(
        codex_llm_port,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )
    monkeypatch.setattr(codex_llm_port.time, "time", lambda: 1000)
    monkeypatch.setattr(
        codex_llm_port.urllib.request,
        "urlopen",
        lambda request, timeout: _FakeHTTPResponse(
            {
                "access_token": _token_with_account_id("account-2"),
                "refresh_token": "new-refresh-token",
                "expires_in": 600,
                "id_token": "new-id-token",
                "token_type": "bearer",
                "scope": "openid profile email offline_access",
            }
        ),
    )
    llm = CodexLLMPort(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_datasource=datasource,
    )

    llm.generate(
        CodexLLMRequest(
            messages=(LLMUserMessage("hello"),),
            model=AgentCodexLLMModel.GPT_5_4,
            parallel_tool_calls=True,
        )
    )

    assert _FakeOpenAI.instances[0].kwargs["api_key"] == _token_with_account_id("account-2")
    assert _FakeOpenAI.instances[0].kwargs["default_headers"]["ChatGPT-Account-ID"] == "account-2"
    assert datasource.saved_credentials_file == "/tmp/openai-codex.json"


def test_codex_llm_port_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeOpenAI.instances = []
    _FakeOpenAI.events = []
    _FakeOpenAI.error_after_events = None
    datasource = _FakeCredentialsDatasource()
    requests: list[object] = []
    monkeypatch.setattr(
        codex_llm_port,
        "_load_openai_client_class",
        lambda: _FakeOpenAI,
    )

    def fake_urlopen(request: object, timeout: int) -> _FakeHTTPResponse:
        requests.append(request)
        assert timeout == 120
        return _FakeHTTPResponse(
            {
                "access_token": _token_with_account_id("account-2"),
                "refresh_token": "new-refresh-token",
                "expires_in": 600,
                "id_token": "new-id-token",
                "token_type": "bearer",
                "scope": "openid profile email offline_access",
            }
        )

    monkeypatch.setattr(
        codex_llm_port.urllib.request,
        "urlopen",
        fake_urlopen,
    )
    llm = CodexLLMPort(
        credentials_file="/tmp/openai-codex.json",
        timeout_seconds=120,
        credentials_datasource=datasource,
    )

    token = llm._refresh_token(datasource.credentials)

    request = requests[0]
    form = parse_qs(request.data.decode("utf-8"))
    assert request.full_url == codex_llm_port.CODEX_TOKEN_URL
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Content-type"] == "application/x-www-form-urlencoded"
    assert request.headers["User-agent"] == codex_llm_port.CODEX_AUTH_USER_AGENT
    assert form == {
        "grant_type": ["refresh_token"],
        "refresh_token": ["refresh-token"],
        "client_id": ["client-1"],
    }
    assert datasource.saved_token_response == {
        "access_token": _token_with_account_id("account-2"),
        "refresh_token": "new-refresh-token",
        "expires_in": 600,
        "id_token": "new-id-token",
        "token_type": "bearer",
        "scope": "openid profile email offline_access",
    }
    assert token.access_token == _token_with_account_id("account-2")
    assert token.account_id == "account-2"
    assert datasource.saved_credentials_file == "/tmp/openai-codex.json"


def _codex_credentials(
    *,
    access_token: str | None = None,
    refresh_token: str = "refresh-token",
    expires_in: int = 2,
    expires_at: int = 9_999_999_999,
    id_token: str = "id-token",
) -> CodexCredentials:
    return CodexCredentials(
        access_token=access_token or _token_with_account_id("account-1"),
        auth_mode="chatgpt",
        client_id="client-1",
        created_at=1,
        expires_at=expires_at,
        expires_in=expires_in,
        id_token=id_token,
        redirect_uri="http://localhost:1455/auth/callback",
        refresh_token=refresh_token,
        scope="openid profile email offline_access",
        source="skiller-openai-auth",
        token_type="bearer",
    )


def _token_with_account_id(account_id: str) -> str:
    payload = json.dumps(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": account_id,
            }
        }
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"
