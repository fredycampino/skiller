from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMToolChoiceMode, LLMUserMessage
from skiller.domain.agent.llm.provider_catalog import (
    LLMApiKeySource,
    LLMApiKeySourceType,
    LLMModelDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.domain.agent.llm.request import OpenAILLMRequest
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.default_llm_client_resolver import DefaultLLMClientResolver
from skiller.infrastructure.llm.openai.openai_api_key_datasource import OpenAIApiKeyDatasource

pytestmark = pytest.mark.e2e

UNAUTHORIZED_API_KEY_LOG_FILE = (
    Path(__file__).resolve().parents[2] / "logs" / "request_invalid_api.json"
)


class _WeatherTool(ToolDefinition[ToolRequest]):
    name = "get_weather"
    description = "Returns the current weather for a city."

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            }
        )

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]:
        _ = input
        return ToolRequestResult.valid(ToolRequest())


def _require_e2e_enabled() -> None:
    if os.environ.get("RUN_ADAPTER_E2E") == "1":
        return
    if os.environ.get("RUN_OPENAI_ADAPTER_E2E") == "1":
        return
    pytest.skip("set RUN_ADAPTER_E2E=1 or RUN_OPENAI_ADAPTER_E2E=1")


def _api_key() -> str:
    api_key_file = os.environ.get("OPENAI_E2E_API_KEY_FILE")
    if api_key_file is not None and api_key_file.strip():
        path = Path(api_key_file).expanduser()
        if not path.is_file():
            pytest.skip(f"OPENAI_E2E_API_KEY_FILE does not exist: {path}")
        api_key = path.read_text(encoding="utf-8").strip()
        if api_key:
            return api_key
        pytest.skip(f"OPENAI_E2E_API_KEY_FILE is empty: {path}")
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key is not None and api_key.strip():
        return api_key
    pytest.skip("OPENAI_API_KEY is not configured")


def _model(*, max_output_tokens: int | None = None) -> LLMModelDefinition:
    return LLMModelDefinition(
        model=os.environ.get("OPENAI_E2E_MODEL", "gpt-4.1-mini"),
        context_window_tokens=int(os.environ.get("OPENAI_E2E_CONTEXT_WINDOW_TOKENS", "1000000")),
        max_output_tokens=max_output_tokens,
    )


def _invalid_model() -> LLMModelDefinition:
    model = os.environ.get("OPENAI_E2E_INVALID_MODEL")
    if model is None or not model.strip():
        pytest.skip("OPENAI_E2E_INVALID_MODEL is not configured")
    return LLMModelDefinition(
        model=model,
        context_window_tokens=int(os.environ.get("OPENAI_E2E_CONTEXT_WINDOW_TOKENS", "1000000")),
        max_output_tokens=None,
    )


def _extra_body() -> Mapping[str, object] | None:
    raw_extra_body = os.environ.get("OPENAI_E2E_EXTRA_BODY")
    if raw_extra_body is None or not raw_extra_body.strip():
        return None
    extra_body = json.loads(raw_extra_body)
    if not isinstance(extra_body, Mapping):
        raise ValueError("OPENAI_E2E_EXTRA_BODY must be a JSON object")
    return extra_body


def _provider(*, api_key: str) -> OpenAILLMProviderDefinition:
    return OpenAILLMProviderDefinition(
        name=os.environ.get("OPENAI_E2E_PROVIDER", "openai-e2e"),
        timeout_seconds=float(os.environ.get("OPENAI_E2E_TIMEOUT_SECONDS", "60")),
        models=(_model(),),
        enabled=True,
        base_url=os.environ.get("OPENAI_E2E_BASE_URL", "https://api.openai.com/v1"),
        temperature=float(os.environ.get("OPENAI_E2E_TEMPERATURE", "0")),
        top_p=float(os.environ.get("OPENAI_E2E_TOP_P", "1")),
        parallel_tool_calls=True,
        tool_choice=LLMToolChoiceMode.AUTO,
        api_key_source=LLMApiKeySource(
            type=LLMApiKeySourceType.VALUE,
            value=api_key,
        ),
        options=_extra_body() or {},
    )


def _client(provider: OpenAILLMProviderDefinition):
    return DefaultLLMClientResolver(
        api_key_datasource=OpenAIApiKeyDatasource(env=os.environ),
    ).resolve(provider)


def test_openai_llm_port_returns_stop() -> None:
    _require_e2e_enabled()
    model = _model()
    provider = _provider(api_key=_api_key())

    response = _client(provider).generate(
        OpenAILLMRequest(
            model=model,
            messages=(LLMUserMessage("Reply with exactly: OPENAI-ADAPTER-STOP"),),
            tool_choice=LLMToolChoiceMode.AUTO,
            temperature=provider.temperature,
            top_p=provider.top_p,
            parallel_tool_calls=provider.parallel_tool_calls,
        )
    )

    assert response.finish_type == LLMFinishType.STOP
    assert response.error is None


def test_openai_llm_port_returns_invalid_response_length() -> None:
    _require_e2e_enabled()
    model = _model(
        max_output_tokens=int(os.environ.get("OPENAI_E2E_LENGTH_MAX_OUTPUT_TOKENS", "1"))
    )
    provider = _provider(api_key=_api_key())

    response = _client(provider).generate(
        OpenAILLMRequest(
            model=model,
            messages=(LLMUserMessage("Write a detailed explanation with at least 100 words."),),
            tool_choice=LLMToolChoiceMode.AUTO,
            temperature=provider.temperature,
            top_p=provider.top_p,
            parallel_tool_calls=provider.parallel_tool_calls,
        )
    )

    assert response.finish_type == LLMFinishType.INVALID_RESPONSE_LENGTH
    assert response.error == "OpenAI response was truncated due to length"


def test_openai_llm_port_returns_tool_calls() -> None:
    _require_e2e_enabled()
    model = _model()
    provider = _provider(api_key=_api_key())

    response = _client(provider).generate(
        OpenAILLMRequest(
            model=model,
            messages=(LLMUserMessage("What is the weather in Madrid?"),),
            tools=(_WeatherTool(),),
            tool_choice=LLMToolChoiceMode.REQUIRED,
            temperature=provider.temperature,
            top_p=provider.top_p,
            parallel_tool_calls=provider.parallel_tool_calls,
        )
    )

    assert response.finish_type == LLMFinishType.TOOL_CALLS
    assert response.error is None


def test_openai_llm_port_returns_unauthorized_api_key_error() -> None:
    _require_e2e_enabled()
    model = _model()
    provider = _provider(api_key="skiller-e2e-unauthorized-api-key")

    response = _client(provider).generate(
        OpenAILLMRequest(
            model=model,
            messages=(LLMUserMessage("Reply with exactly: UNAUTHORIZED-API-KEY"),),
            tool_choice=LLMToolChoiceMode.AUTO,
            temperature=provider.temperature,
            top_p=provider.top_p,
            parallel_tool_calls=provider.parallel_tool_calls,
            log_request_file=str(UNAUTHORIZED_API_KEY_LOG_FILE),
            log_override_file=True,
        )
    )

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error is not None


def test_openai_llm_port_returns_request_error_for_invalid_model() -> None:
    _require_e2e_enabled()
    provider = _provider(api_key=_api_key())

    response = _client(provider).generate(
        OpenAILLMRequest(
            model=_invalid_model(),
            messages=(LLMUserMessage("Reply with exactly: OPENAI-ADAPTER-INVALID-MODEL"),),
            tool_choice=LLMToolChoiceMode.AUTO,
            temperature=provider.temperature,
            top_p=provider.top_p,
            parallel_tool_calls=provider.parallel_tool_calls,
        )
    )

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "request_failed"
