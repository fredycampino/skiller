from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMUserMessage
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.bedrock.bedrock_mapper import BedrockMapper
from skiller.infrastructure.llm.bedrock.bedrock_request_logger import (
    BedrockFileLLMRequestLogger,
)
from skiller.infrastructure.llm.bedrock.collect_converse_response import (
    CollectConverseResponse,
)
from skiller.infrastructure.llm.bedrock.converse_llm_port import ConverseLLMPort
from skiller.infrastructure.llm.bedrock.converse_mapper import ConverseMapper
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper

pytestmark = pytest.mark.e2e

SUCCESS_LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "converse_success.json"


class _NoopRequestLogger:
    def log_request(self, **_kwargs: object) -> None:
        pass

    def log_response(self, **_kwargs: object) -> None:
        pass

    def log_error(self, **_kwargs: object) -> None:
        pass


class _CommandTool(ToolDefinition[ToolRequest]):
    name = "run_command"
    description = "Runs a command and returns its result."

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            }
        )

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]:
        _ = input
        return ToolRequestResult.valid(ToolRequest())


def _require_e2e_enabled() -> None:
    if os.environ.get("RUN_ADAPTER_E2E") == "1":
        return
    if os.environ.get("RUN_BEDROCK_ADAPTER_E2E") == "1":
        return
    pytest.skip("set RUN_ADAPTER_E2E=1 or RUN_BEDROCK_ADAPTER_E2E=1")


def _profile() -> str:
    profile = os.environ.get("BEDROCK_E2E_PROFILE") or os.environ.get("AGENT_BEDROCK_PROFILE")
    if profile is not None and profile.strip():
        return profile
    pytest.skip("BEDROCK_E2E_PROFILE is not configured")


def _model(*, max_output_tokens: int | None = None) -> LLMModelDefinition:
    return LLMModelDefinition(
        model=os.environ.get("BEDROCK_E2E_MODEL", "us.anthropic.claude-opus-4-6-v1"),
        context_window_tokens=int(os.environ.get("BEDROCK_E2E_CONTEXT_WINDOW_TOKENS", "200000")),
        max_output_tokens=max_output_tokens,
    )


def _unavailable_model(*, max_output_tokens: int | None = None) -> LLMModelDefinition:
    model = os.environ.get("BEDROCK_E2E_UNAVAILABLE_MODEL")
    if model is None or not model.strip():
        pytest.skip("BEDROCK_E2E_UNAVAILABLE_MODEL is not configured")
    return LLMModelDefinition(
        model=model,
        context_window_tokens=int(os.environ.get("BEDROCK_E2E_CONTEXT_WINDOW_TOKENS", "200000")),
        max_output_tokens=max_output_tokens,
    )


def _invalid_model(*, max_output_tokens: int | None = None) -> LLMModelDefinition:
    model = os.environ.get("BEDROCK_E2E_INVALID_MODEL")
    if model is None or not model.strip():
        pytest.skip("BEDROCK_E2E_INVALID_MODEL is not configured")
    return LLMModelDefinition(
        model=model,
        context_window_tokens=int(os.environ.get("BEDROCK_E2E_CONTEXT_WINDOW_TOKENS", "200000")),
        max_output_tokens=max_output_tokens,
    )


def _port(*, profile: str, request_logger: LLMRequestLogger) -> ConverseLLMPort:
    usage_mapper = DefaultLLMUsageMapper()
    return ConverseLLMPort(
        profile=profile,
        timeout_seconds=float(os.environ.get("BEDROCK_E2E_TIMEOUT_SECONDS", "120")),
        request_logger=request_logger,
        request_mapper=BedrockMapper(),
        response_mapper=ConverseMapper(usage_mapper=usage_mapper),
        collector=CollectConverseResponse(),
    )


def test_converse_llm_port_returns_stop() -> None:
    _require_e2e_enabled()

    response = _port(profile=_profile(), request_logger=_NoopRequestLogger()).generate(
        BedrockLLMRequest(
            model=_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: BEDROCK-CONVERSE-STOP"),),
        )
    )

    assert response.finish_type == LLMFinishType.STOP
    assert response.content is not None
    assert response.usage is not None


def test_converse_llm_port_returns_tool_calls() -> None:
    _require_e2e_enabled()

    response = _port(profile=_profile(), request_logger=_NoopRequestLogger()).generate(
        BedrockLLMRequest(
            model=_model(max_output_tokens=None),
            messages=(
                LLMUserMessage(
                    "You must call run_command with command 'pwd'. Do not answer with text."
                ),
            ),
            tools=(_CommandTool(),),
        )
    )

    assert response.finish_type == LLMFinishType.TOOL_CALLS
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].function.name == "run_command"
    assert json.loads(response.tool_calls[0].function.arguments_json) == {"command": "pwd"}
    assert response.usage is not None


def test_converse_llm_port_returns_invalid_response_length() -> None:
    _require_e2e_enabled()

    response = _port(profile=_profile(), request_logger=_NoopRequestLogger()).generate(
        BedrockLLMRequest(
            model=_model(max_output_tokens=1),
            messages=(LLMUserMessage("Write a detailed explanation with at least 100 words."),),
        )
    )

    assert response.finish_type == LLMFinishType.INVALID_RESPONSE_LENGTH
    assert response.error_code == "response_length"


def test_converse_llm_port_logs_received_stream() -> None:
    _require_e2e_enabled()

    response = _port(
        profile=_profile(),
        request_logger=BedrockFileLLMRequestLogger(),
    ).generate(
        BedrockLLMRequest(
            model=_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: BEDROCK-CONVERSE-LOG"),),
            log_request_file=str(SUCCESS_LOG_FILE),
            log_override_file=True,
            log_streaming=True,
        )
    )

    assert response.finish_type == LLMFinishType.STOP
    log = json.loads(SUCCESS_LOG_FILE.read_text(encoding="utf-8"))
    assert isinstance(log["response"], dict)
    assert isinstance(log["response"]["stream"], list)
    assert log["response"]["stream"]


def test_converse_llm_port_returns_unauthorized_or_forbidden_error() -> None:
    _require_e2e_enabled()
    profile = os.environ.get("BEDROCK_E2E_UNAUTHORIZED_PROFILE")
    if profile is None or not profile.strip():
        pytest.skip("BEDROCK_E2E_UNAUTHORIZED_PROFILE is not configured")

    response = _port(profile=profile, request_logger=_NoopRequestLogger()).generate(
        BedrockLLMRequest(
            model=_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: BEDROCK-CONVERSE-UNAUTHORIZED"),),
        )
    )

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code in ("unauthorized", "forbidden")


def test_converse_llm_port_returns_model_not_available_error() -> None:
    _require_e2e_enabled()

    response = _port(profile=_profile(), request_logger=_NoopRequestLogger()).generate(
        BedrockLLMRequest(
            model=_unavailable_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: BEDROCK-CONVERSE-MODEL"),),
        )
    )

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "model_not_available"


def test_converse_llm_port_returns_invalid_model_error() -> None:
    _require_e2e_enabled()

    response = _port(profile=_profile(), request_logger=_NoopRequestLogger()).generate(
        BedrockLLMRequest(
            model=_invalid_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: BEDROCK-CONVERSE-INVALID-MODEL"),),
        )
    )

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "invalid_model"
