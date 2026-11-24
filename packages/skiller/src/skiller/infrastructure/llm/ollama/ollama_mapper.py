import json
from dataclasses import asdict, dataclass
from uuid import uuid4

from ollama import ChatResponse

from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import (
    LLMAssistantMessage,
    LLMGenerationMetrics,
    LLMResponse,
    LLMResponseFormatType,
    LLMToolCall,
    LLMToolCallFunction,
    LLMToolMessage,
)
from skiller.domain.agent.llm.provider_ollama import OllamaLLMRequest
from skiller.infrastructure.llm.mapper.llm_protocol_mapper import LLMProtocolMapper
from skiller.infrastructure.llm.mapper.llm_usage_mapper import LLMProviderUsage, LLMUsageMapper


@dataclass(frozen=True)
class OllamaMapper(LLMProtocolMapper[OllamaLLMRequest, ChatResponse]):
    usage_mapper: LLMUsageMapper
    keep_alive: str | int | None

    def to_kwargs(self, request: OllamaLLMRequest) -> dict[str, object]:
        model = request.model
        if request.effort is not None and (
            type(request.effort) is not int or not 1 <= request.effort <= 5
        ):
            raise ValueError("Ollama effort must be an integer from 1 to 5")
        messages = []
        for message in request.messages:
            payload: dict[str, object] = {
                "role": message.role.value,
                "content": message.content or "",
            }
            if isinstance(message, LLMAssistantMessage) and message.tool_calls:
                payload["tool_calls"] = [
                    {
                        "function": {
                            "name": call.function.name,
                            "arguments": json.loads(call.function.arguments_json),
                        }
                    }
                    for call in message.tool_calls
                ]
            if isinstance(message, LLMToolMessage):
                name = message.name
                if name is None:
                    name = next(
                        (
                            call.function.name
                            for entry in request.messages
                            if isinstance(entry, LLMAssistantMessage)
                            for call in entry.tool_calls
                            if call.id == message.tool_call_id
                        ),
                        None,
                    )
                if name is None:
                    raise ValueError("Ollama tool result requires a matching tool call or name")
                payload["tool_name"] = name
            messages.append(payload)
        options = (
            {key: value for key, value in asdict(model.params).items() if value is not None}
            if model.params is not None
            else {}
        )
        if "stop" in options:
            options["stop"] = list(options["stop"])
        options["num_ctx"] = request.model.model_context_window_tokens
        if request.model.max_output_tokens is not None:
            options["num_predict"] = request.model.max_output_tokens
        kwargs: dict[str, object] = {
            "model": request.model.value,
            "messages": messages,
            "options": options,
            "stream": False,
        }
        if self.keep_alive is not None:
            kwargs["keep_alive"] = self.keep_alive
        if request.effort is not None and model.effort_mapping is not None:
            kwargs["think"] = model.effort_mapping[request.effort - 1]
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": dict(tool.schema().value),
                    },
                }
                for tool in request.tools
            ]
        if request.response_format is not None:
            format = request.response_format
            if format.type == LLMResponseFormatType.JSON_OBJECT:
                kwargs["format"] = "json"
            elif format.type == LLMResponseFormatType.JSON_SCHEMA:
                if format.json_schema is None:
                    raise ValueError("Ollama JSON schema format requires a schema")
                kwargs["format"] = dict(format.json_schema)
        return kwargs

    def to_response(self, raw_response: ChatResponse, *, request: OllamaLLMRequest) -> LLMResponse:
        tool_calls = tuple(
            LLMToolCall(
                id=f"ollama_{uuid4().hex}",
                function=LLMToolCallFunction(
                    name=call.function.name,
                    arguments_json=json.dumps(call.function.arguments, ensure_ascii=False),
                ),
            )
            for call in raw_response.message.tool_calls or ()
        )
        content = raw_response.message.content
        error = None
        error_code = None
        if not raw_response.done:
            finish = LLMFinishType.ERROR_MALFORMED_RESPONSE
            error, error_code = "Ollama response is incomplete", "incomplete_response"
        elif raw_response.done_reason == "length":
            finish = LLMFinishType.INVALID_RESPONSE_LENGTH
            error, error_code = "Ollama response was truncated due to length", "response_length"
        elif raw_response.done_reason != "stop":
            finish = LLMFinishType.UNKNOWN
            error, error_code = (
                "Ollama response has an unknown finish reason",
                "unknown_finish_reason",
            )
        elif tool_calls:
            finish = LLMFinishType.TOOL_CALLS
        elif content and content.strip():
            finish = LLMFinishType.STOP
        else:
            finish = LLMFinishType.ERROR_MISSING_CONTENT
            error, error_code = "Ollama response missing content", "missing_content"
        prompt, output = raw_response.prompt_eval_count, raw_response.eval_count
        usage = self.usage_mapper.to_usage(
            LLMProviderUsage(
                prompt_tokens=prompt,
                output_tokens=output,
                total_tokens=prompt + output if prompt is not None and output is not None else None,
                cache_read_tokens=None,
                cache_write_tokens=None,
            ),
            request=request,
        )
        generation_metrics = LLMGenerationMetrics(
            total_duration_ns=raw_response.total_duration,
            model_load_duration_ns=raw_response.load_duration,
            input_tokens=raw_response.prompt_eval_count,
            input_processing_duration_ns=raw_response.prompt_eval_duration,
            output_tokens=raw_response.eval_count,
            output_generation_duration_ns=raw_response.eval_duration,
        )
        return LLMResponse(
            generation_metrics=generation_metrics,
            model=request.model,
            finish_type=finish,
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            error=error,
            error_code=error_code,
        )
