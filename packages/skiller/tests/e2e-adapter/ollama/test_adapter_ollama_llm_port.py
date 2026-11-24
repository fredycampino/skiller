import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMSystemMessage,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import LLMModelParams, OllamaLLMModelDefinition
from skiller.domain.agent.llm.provider_ollama import OllamaLLMRequest
from skiller.domain.tool.tool_contract import (
    ToolDefinition,
    ToolInput,
    ToolRequest,
    ToolRequestResult,
    ToolSchema,
)
from skiller.infrastructure.llm.logger.request_logger import FileLLMRequestLogger
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper

pytestmark = pytest.mark.e2e


class _WeatherTool(ToolDefinition[ToolRequest]):
    name = "get_weather"
    description = "Returns the current weather for a city."

    def schema(self) -> ToolSchema:
        return ToolSchema(
            value={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
                "additionalProperties": False,
            }
        )

    def request(self, input: ToolInput) -> ToolRequestResult[ToolRequest]:
        return ToolRequestResult.valid(ToolRequest())


@pytest.fixture
def port():
    if not any(
        os.environ.get(flag) == "1" for flag in ("RUN_ADAPTER_E2E", "RUN_OLLAMA_ADAPTER_E2E")
    ):
        pytest.skip("set RUN_ADAPTER_E2E=1 or RUN_OLLAMA_ADAPTER_E2E=1")
    pytest.importorskip("ollama")
    from skiller.infrastructure.llm.ollama.ollama_llm_port import OllamaLLMPort
    from skiller.infrastructure.llm.ollama.ollama_mapper import OllamaMapper

    return OllamaLLMPort(
        base_url=os.environ.get("OLLAMA_E2E_BASE_URL", "http://127.0.0.1:11434"),
        timeout_seconds=float(os.environ.get("OLLAMA_E2E_TIMEOUT_SECONDS", "600")),
        mapper=OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive=None),
        request_logger=FileLLMRequestLogger(),
    )


@pytest.fixture
def model() -> OllamaLLMModelDefinition:
    name = os.environ.get("OLLAMA_E2E_MODEL")
    if not name:
        pytest.skip("set OLLAMA_E2E_MODEL to an installed tool-capable model")
    return OllamaLLMModelDefinition(
        model=name,
        context_window_tokens=int(os.environ.get("OLLAMA_E2E_CONTEXT_WINDOW_TOKENS", "32768")),
        max_output_tokens=1024,
        params=LLMModelParams(
            temperature=0, top_p=None, top_k=None, seed=None, repeat_penalty=None, stop=None
        ),
        effort_mapping=None,
    )


def test_port_returns_text_and_logs_native_metrics(port, model, tmp_path: Path) -> None:
    path = tmp_path / "text.json"
    response = port.generate(
        OllamaLLMRequest(
            model=model,
            messages=(LLMUserMessage("Reply with a short greeting."),),
            log_request_file=str(path),
        )
    )
    assert response.finish_type == LLMFinishType.STOP, response.error
    assert response.has_text_content
    assert response.usage is not None
    assert response.usage.prompt_tokens > 0
    assert response.usage.output_tokens > 0
    assert (
        response.usage.total_tokens == response.usage.prompt_tokens + response.usage.output_tokens
    )
    log = json.loads(path.read_text())
    assert log["error"] is None
    assert log["request"]["options"]["num_ctx"] == model.context_window_tokens
    assert log["response"]["eval_count"] == response.usage.output_tokens
    for field in ("total_duration", "eval_duration", "prompt_eval_duration"):
        assert log["response"][field] > 0
    assert log["response"]["load_duration"] >= 0
    metrics = response.generation_metrics
    assert metrics is not None
    assert metrics.input_tokens == response.usage.prompt_tokens
    assert metrics.output_tokens == response.usage.output_tokens
    assert metrics.total_duration_ns == log["response"]["total_duration"]
    assert metrics.model_load_duration_ns == log["response"]["load_duration"]
    assert metrics.input_processing_duration_ns == log["response"]["prompt_eval_duration"]
    assert metrics.output_generation_duration_ns == log["response"]["eval_duration"]


def test_port_completes_tool_round_trip(port, model, tmp_path: Path) -> None:
    tool = _WeatherTool()
    messages = (
        LLMSystemMessage(
            "Use get_weather for weather questions. After receiving its result, "
            "answer briefly without further tool calls."
        ),
        LLMUserMessage("What is the current weather in Madrid? Call get_weather with city Madrid."),
    )
    path = tmp_path / "tool.json"
    response = port.generate(
        OllamaLLMRequest(
            model=model,
            messages=messages,
            tools=(tool,),
            log_request_file=str(path),
        )
    )
    assert response.finish_type == LLMFinishType.TOOL_CALLS, response.error or response.content
    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.id
    assert call.function.name == "get_weather"
    assert json.loads(call.function.arguments_json) == {"city": "Madrid"}
    assert json.loads(path.read_text())["response"]["eval_duration"] > 0
    # Supply a simulated result; no external tool is executed.
    final = port.generate(
        OllamaLLMRequest(
            model=model,
            messages=messages
            + (
                LLMAssistantMessage(content=response.content, tool_calls=response.tool_calls),
                LLMToolMessage(
                    content='{"temperature_c": 21, "condition": "sunny"}', tool_call_id=call.id
                ),
            ),
            tools=(tool,),
        )
    )
    assert final.finish_type == LLMFinishType.STOP, final.error or final.content
    assert final.has_text_content
    assert not final.tool_calls
    assert "21" in final.content


def test_port_returns_error_for_missing_model(port, model, tmp_path: Path) -> None:
    path = tmp_path / "error.json"
    response = port.generate(
        OllamaLLMRequest(
            model=replace(model, model="skiller-e2e-nonexistent-model:missing"),
            messages=(LLMUserMessage("Hello"),),
            log_request_file=str(path),
        )
    )
    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert response.error_code == "request_failed"
    assert response.error
    log = json.loads(path.read_text())
    assert log["response"] is None
    assert log["error"] == response.error
