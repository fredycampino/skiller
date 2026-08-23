from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import LLMModelDefinition
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentialsDatasource,
)
from skiller.infrastructure.llm.codex.codex_mapper import CodexMapper
from skiller.infrastructure.llm.codex.codex_model_capabilities import (
    CodexModelCapabilitiesResolver,
)
from skiller.infrastructure.llm.codex.codex_request_logger import CodexFileLLMRequestLogger
from skiller.infrastructure.llm.codex.codex_turn_session import CodexTurnSessionManager
from skiller.infrastructure.llm.codex.collect_codex_response import CollectCodexResponse
from skiller.infrastructure.llm.codex.responses_general_mapper import ResponsesGeneralMapper
from skiller.infrastructure.llm.codex.responses_lite_mapper import ResponsesLiteMapper
from skiller.infrastructure.llm.codex.responses_llm_port import ResponsesLLMPort
from skiller.infrastructure.llm.codex.responses_mapper import ResponsesMapper
from skiller.infrastructure.llm.logger.request_logger import LLMRequestLogger
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper

pytestmark = pytest.mark.e2e

SUCCESS_LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "codex_response.json"
CONTINUATION_LOG_FILE = (
    Path(__file__).resolve().parents[2] / "logs" / "codex_lite_continuation.json"
)
CONTINUATION_SEED_LOG_FILE = (
    Path(__file__).resolve().parents[2] / "logs" / "codex_lite_continuation_seed.json"
)


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
    if os.environ.get("RUN_CODEX_ADAPTER_E2E") == "1":
        return
    pytest.skip("set RUN_ADAPTER_E2E=1 or RUN_CODEX_ADAPTER_E2E=1")


def _credentials_file() -> str:
    path = Path(
        os.environ.get(
            "CODEX_E2E_CREDENTIALS_FILE",
            "~/.skiller/secrets/openai-codex.json",
        )
    ).expanduser()
    if path.is_file():
        return str(path)
    pytest.skip(f"CODEX_E2E_CREDENTIALS_FILE does not exist: {path}")


def _model(*, value: str, max_output_tokens: int | None) -> LLMModelDefinition:
    return LLMModelDefinition(
        model=value,
        context_window_tokens=int(os.environ.get("CODEX_E2E_CONTEXT_WINDOW_TOKENS", "1050000")),
        max_output_tokens=max_output_tokens,
    )


def _generic_model(*, max_output_tokens: int | None) -> LLMModelDefinition:
    return _model(
        value=os.environ.get("CODEX_E2E_GENERIC_MODEL", "gpt-5.5"),
        max_output_tokens=max_output_tokens,
    )


def _lite_model(*, max_output_tokens: int | None) -> LLMModelDefinition:
    return _model(
        value=os.environ.get("CODEX_E2E_LITE_MODEL", "gpt-5.6-luna"),
        max_output_tokens=max_output_tokens,
    )


def _invalid_model(*, max_output_tokens: int | None) -> LLMModelDefinition:
    value = os.environ.get("CODEX_E2E_INVALID_MODEL")
    if value is None or not value.strip():
        pytest.skip("CODEX_E2E_INVALID_MODEL is not configured")
    return _model(value=value, max_output_tokens=max_output_tokens)


def _port(
    *,
    credentials_file: str,
    request_logger: LLMRequestLogger,
) -> ResponsesLLMPort:
    usage_mapper = DefaultLLMUsageMapper()
    request_mapper = CodexMapper(
        capabilities_resolver=CodexModelCapabilitiesResolver(),
        responses_mapper=ResponsesGeneralMapper(),
        responses_lite_mapper=ResponsesLiteMapper(),
    )
    return ResponsesLLMPort(
        credentials_file=credentials_file,
        timeout_seconds=float(os.environ.get("CODEX_E2E_TIMEOUT_SECONDS", "120")),
        credentials_datasource=CodexCredentialsDatasource(),
        request_logger=request_logger,
        request_mapper=request_mapper,
        response_mapper=ResponsesMapper(usage_mapper=usage_mapper),
        collector=CollectCodexResponse(),
        turn_session_manager=CodexTurnSessionManager(),
    )


def _request(
    *,
    model: LLMModelDefinition,
    messages: tuple[LLMUserMessage | LLMAssistantMessage | LLMToolMessage, ...],
    session_id: str,
    tools: tuple[ToolDefinition[ToolRequest], ...] = (),
    log_request_file: str | None = None,
    log_streaming: bool = False,
) -> CodexLLMRequest:
    return CodexLLMRequest(
        model=model,
        messages=messages,
        parallel_tool_calls=False,
        session_id=session_id,
        tools=tools,
        log_request_file=log_request_file,
        log_override_file=True,
        log_streaming=log_streaming,
    )


def test_responses_llm_port_returns_generic_stop() -> None:
    _require_e2e_enabled()
    port = _port(credentials_file=_credentials_file(), request_logger=_NoopRequestLogger())

    response = port.generate(
        _request(
            model=_generic_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: CODEX-GENERIC-STOP"),),
            session_id="codex-e2e-generic-stop",
        )
    )

    assert response.finish_type == LLMFinishType.STOP
    assert response.error is None


def test_responses_llm_port_returns_generic_tool_calls() -> None:
    _require_e2e_enabled()
    port = _port(credentials_file=_credentials_file(), request_logger=_NoopRequestLogger())

    response = port.generate(
        _request(
            model=_generic_model(max_output_tokens=None),
            messages=(
                LLMUserMessage(
                    "Call run_command exactly once with command 'pwd'. Do not answer with text."
                ),
            ),
            session_id="codex-e2e-generic-tools",
            tools=(_CommandTool(),),
        )
    )

    assert response.finish_type == LLMFinishType.TOOL_CALLS
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].function.name == "run_command"
    assert json.loads(response.tool_calls[0].function.arguments_json) == {"command": "pwd"}


def test_responses_llm_port_ignores_model_max_output_tokens_for_generic() -> None:
    _require_e2e_enabled()
    port = _port(credentials_file=_credentials_file(), request_logger=_NoopRequestLogger())

    response = port.generate(
        _request(
            model=_generic_model(max_output_tokens=32),
            messages=(
                LLMUserMessage(
                    "Write continuous text of at least 250 characters. Do not use tools."
                ),
            ),
            session_id="codex-e2e-generic-length",
        )
    )

    assert response.finish_type == LLMFinishType.STOP
    assert response.error is None
    assert response.content is not None
    assert len(response.content) >= 250


def test_responses_llm_port_returns_lite_stop() -> None:
    _require_e2e_enabled()
    port = _port(credentials_file=_credentials_file(), request_logger=_NoopRequestLogger())

    response = port.generate(
        _request(
            model=_lite_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: CODEX-LITE-STOP"),),
            session_id="codex-e2e-lite-stop",
        )
    )

    assert response.finish_type == LLMFinishType.STOP
    assert response.error is None


def test_responses_llm_port_returns_lite_tool_calls() -> None:
    _require_e2e_enabled()
    port = _port(credentials_file=_credentials_file(), request_logger=_NoopRequestLogger())

    response = port.generate(
        _request(
            model=_lite_model(max_output_tokens=None),
            messages=(
                LLMUserMessage(
                    "Call run_command exactly once with command 'pwd'. Do not answer with text."
                ),
            ),
            session_id="codex-e2e-lite-tools",
            tools=(_CommandTool(),),
        )
    )

    assert response.finish_type == LLMFinishType.TOOL_CALLS
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].function.name == "run_command"
    assert json.loads(response.tool_calls[0].function.arguments_json) == {"command": "pwd"}


def test_responses_llm_port_ignores_model_max_output_tokens_for_lite() -> None:
    _require_e2e_enabled()
    port = _port(credentials_file=_credentials_file(), request_logger=_NoopRequestLogger())

    response = port.generate(
        _request(
            model=_lite_model(max_output_tokens=32),
            messages=(
                LLMUserMessage(
                    "Write continuous text of at least 250 characters. Do not use tools."
                ),
            ),
            session_id="codex-e2e-lite-length",
        )
    )

    assert response.finish_type == LLMFinishType.STOP
    assert response.error is None
    assert response.content is not None
    assert len(response.content) >= 250


def test_responses_llm_port_continues_lite_tool_call_with_prior_result() -> None:
    _require_e2e_enabled()
    port = _port(
        credentials_file=_credentials_file(),
        request_logger=CodexFileLLMRequestLogger(),
    )
    model = _lite_model(max_output_tokens=None)
    session_id = "codex-e2e-lite-continuation"
    initial = port.generate(
        _request(
            model=model,
            messages=(
                LLMUserMessage(
                    "Call run_command exactly once with command 'pwd'. After I provide its "
                    "result, call run_command exactly once with command 'ls <the exact "
                    "result>'. Do not answer with text."
                ),
            ),
            session_id=session_id,
            tools=(_CommandTool(),),
            log_request_file=str(CONTINUATION_SEED_LOG_FILE),
            log_streaming=True,
        )
    )

    assert initial.finish_type == LLMFinishType.TOOL_CALLS
    assert len(initial.tool_calls) == 1
    tool_call = initial.tool_calls[0]
    response = port.generate(
        _request(
            model=model,
            messages=(
                LLMUserMessage(
                    "Call run_command exactly once with command 'pwd'. After I provide its "
                    "result, call run_command exactly once with command 'ls <the exact "
                    "result>'. Do not answer with text."
                ),
                LLMAssistantMessage(tool_calls=initial.tool_calls),
                LLMToolMessage("/workspace", tool_call_id=tool_call.id),
            ),
            session_id=session_id,
            tools=(_CommandTool(),),
            log_request_file=str(CONTINUATION_LOG_FILE),
            log_streaming=True,
        )
    )

    assert response.finish_type == LLMFinishType.TOOL_CALLS
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].function.name == "run_command"
    assert json.loads(response.tool_calls[0].function.arguments_json) == {
        "command": "ls /workspace"
    }


def test_responses_llm_port_returns_unauthorized_credentials_error(tmp_path: Path) -> None:
    _require_e2e_enabled()
    credentials_file = tmp_path / "invalid-codex-credentials.json"
    credentials_file.write_text(
        json.dumps(
            {
                "access_token": "invalid-codex-e2e-token",
                "auth_mode": "chatgpt",
                "client_id": "client-id",
                "created_at": 0,
                "expires_at": 4_102_444_800,
                "expires_in": 3600,
                "id_token": "id-token",
                "redirect_uri": "http://localhost:1455/auth/callback",
                "refresh_token": "refresh-token",
                "scope": "openid profile email offline_access",
                "source": "skiller-e2e",
                "token_type": "bearer",
            }
        ),
        encoding="utf-8",
    )
    port = _port(credentials_file=str(credentials_file), request_logger=_NoopRequestLogger())

    response = port.generate(
        _request(
            model=_generic_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: CODEX-UNAUTHORIZED"),),
            session_id="codex-e2e-unauthorized",
        )
    )

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error is not None
    assert response.error_code == "request_failed"


def test_responses_llm_port_returns_invalid_model_error() -> None:
    _require_e2e_enabled()
    port = _port(credentials_file=_credentials_file(), request_logger=_NoopRequestLogger())

    response = port.generate(
        _request(
            model=_invalid_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: CODEX-INVALID-MODEL"),),
            session_id="codex-e2e-invalid-model",
        )
    )

    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error is not None
    assert response.error_code == "request_failed"


def test_responses_llm_port_logs_received_stream() -> None:
    _require_e2e_enabled()
    port = _port(
        credentials_file=_credentials_file(),
        request_logger=CodexFileLLMRequestLogger(),
    )

    response = port.generate(
        _request(
            model=_generic_model(max_output_tokens=None),
            messages=(LLMUserMessage("Reply with exactly: CODEX-LOG"),),
            session_id="codex-e2e-log",
            log_request_file=str(SUCCESS_LOG_FILE),
            log_streaming=True,
        )
    )

    assert response.finish_type == LLMFinishType.STOP
    log = json.loads(SUCCESS_LOG_FILE.read_text(encoding="utf-8"))
    assert isinstance(log["response"], dict)
    assert isinstance(log["response"]["stream"], list)
    assert log["response"]["stream"]
