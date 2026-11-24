import json
from pathlib import Path

import httpx
import pytest
from ollama import Client

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMGenerationMetrics,
    LLMToolMessage,
    LLMUserMessage,
)
from skiller.domain.agent.llm.provider_catalog import LLMModelParams, OllamaLLMModelDefinition
from skiller.domain.agent.llm.provider_ollama import OllamaLLMRequest
from skiller.infrastructure.llm.logger.request_logger import FileLLMRequestLogger
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper
from skiller.infrastructure.llm.ollama import ollama_llm_port
from skiller.infrastructure.llm.ollama.ollama_llm_port import OllamaLLMPort
from skiller.infrastructure.llm.ollama.ollama_mapper import OllamaMapper

pytestmark = pytest.mark.unit
MODEL = OllamaLLMModelDefinition(
    model="test",
    context_window_tokens=32768,
    max_output_tokens=128,
    params=LLMModelParams(
        temperature=1, top_p=None, top_k=None, seed=None, repeat_penalty=None, stop=None
    ),
    effort_mapping=None,
)


def test_port_completes_tool_round_trip_and_keeps_timings_in_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["stream"] is False
        requests.append(payload)
        assert payload["options"] == {"temperature": 1, "num_ctx": 32768, "num_predict": 128}
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "shell", "arguments": {"command": "ls"}}}],
            }
        else:
            assert payload["messages"][-1] == {
                "role": "tool",
                "content": "file.txt",
                "tool_name": "shell",
            }
            assert payload["messages"][-2]["tool_calls"][0]["function"]["arguments"] == {
                "command": "ls"
            }
            message = {"role": "assistant", "content": "Found file.txt"}
        return httpx.Response(
            200,
            json={
                "message": message,
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 100,
                "eval_count": 20,
                "eval_duration": 1_000_000_000,
                "total_duration": 1_500_000_000,
                "load_duration": 100_000_000,
                "prompt_eval_duration": 400_000_000,
            },
        )

    def client_class(**kwargs):
        assert kwargs == {"host": "http://ollama.test", "timeout": 60}
        return Client(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(ollama_llm_port, "_load_ollama_client_class", lambda: client_class)
    port = OllamaLLMPort(
        base_url="http://ollama.test/",
        timeout_seconds=60,
        request_logger=FileLLMRequestLogger(),
        mapper=OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive=None),
    )
    path = tmp_path / "llm.json"
    messages = (LLMUserMessage("List files"),)
    first = port.generate(
        OllamaLLMRequest(model=MODEL, messages=messages, log_request_file=str(path))
    )
    assert first.finish_type == LLMFinishType.TOOL_CALLS
    assert first.tool_calls[0].id
    assert first.usage.total_tokens == 120
    assert first.generation_metrics == LLMGenerationMetrics(
        total_duration_ns=1_500_000_000,
        model_load_duration_ns=100_000_000,
        input_tokens=100,
        input_processing_duration_ns=400_000_000,
        output_tokens=20,
        output_generation_duration_ns=1_000_000_000,
    )
    assert json.loads(path.read_text())["response"]["eval_duration"] == 1_000_000_000
    final = port.generate(
        OllamaLLMRequest(
            model=MODEL,
            messages=messages
            + (
                LLMAssistantMessage(tool_calls=first.tool_calls),
                LLMToolMessage(content="file.txt", tool_call_id=first.tool_calls[0].id),
            ),
        )
    )
    assert final.finish_type == LLMFinishType.STOP
    assert final.content == "Found file.txt"


@pytest.mark.parametrize(
    "reason,content,done,expected",
    [
        ("length", "partial", True, LLMFinishType.INVALID_RESPONSE_LENGTH),
        ("stop", "", True, LLMFinishType.ERROR_MISSING_CONTENT),
        ("other", "text", True, LLMFinishType.UNKNOWN),
        ("stop", "partial", False, LLMFinishType.ERROR_MALFORMED_RESPONSE),
    ],
)
def test_mapper_classifies_invalid_responses(reason, content, done, expected) -> None:
    from ollama import ChatResponse

    response = OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive=None).to_response(
        ChatResponse(
            message={"role": "assistant", "content": content}, done=done, done_reason=reason
        ),
        request=OllamaLLMRequest(model=MODEL, messages=()),
    )
    assert response.finish_type == expected
    assert response.error
    assert response.usage.total_tokens is None
    assert response.generation_metrics == LLMGenerationMetrics(
        total_duration_ns=None,
        model_load_duration_ns=None,
        input_tokens=None,
        input_processing_duration_ns=None,
        output_tokens=None,
        output_generation_duration_ns=None,
    )


@pytest.mark.parametrize("logging", [True, False])
def test_port_maps_transport_error_and_logs_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logging: bool
) -> None:
    def client_class(**kwargs):
        return Client(
            **kwargs,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(404, json={"error": "model not found"})
            ),
        )

    monkeypatch.setattr(ollama_llm_port, "_load_ollama_client_class", lambda: client_class)
    port = OllamaLLMPort(
        base_url="http://ollama.test",
        timeout_seconds=60,
        request_logger=FileLLMRequestLogger(),
        mapper=OllamaMapper(usage_mapper=DefaultLLMUsageMapper(), keep_alive=None),
    )
    path = tmp_path / "llm.json"
    response = port.generate(
        OllamaLLMRequest(model=MODEL, messages=(), log_request_file=str(path) if logging else None)
    )
    assert response.generation_metrics is None
    assert response.finish_type == LLMFinishType.ERROR_REQUEST_FAILED
    assert "model not found" in response.error
    assert path.exists() is logging
    if logging:
        logged = json.loads(path.read_text())
        assert logged["response"] is None
        assert "model not found" in logged["error"]
