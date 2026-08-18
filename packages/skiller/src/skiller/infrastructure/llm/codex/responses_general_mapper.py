from dataclasses import dataclass

from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.infrastructure.llm.codex.codex_mapper import (
    to_codex_prompt_payload,
    to_codex_response_format_payload,
    to_codex_tool_payload,
)
from skiller.infrastructure.llm.codex.codex_reasoning import (
    CODEX_DEFAULT_REASONING_EFFORT,
)
from skiller.infrastructure.llm.codex.codex_turn_session import CodexTurnSession


@dataclass(frozen=True)
class ResponsesGeneralMapper:
    def to_kwargs(
        self,
        request: CodexLLMRequest,
        *,
        turn_session: CodexTurnSession,
    ) -> dict[str, object]:
        _ = turn_session
        instructions, input_items = to_codex_prompt_payload(request.messages)
        payload: dict[str, object] = {
            "model": request.model.value,
            "instructions": instructions,
            "input": input_items,
            "prompt_cache_key": request.session_id,
            "extra_headers": {
                "session_id": request.session_id,
                "x-client-request-id": request.session_id,
            },
            "store": False,
            "tool_choice": "auto",
            "parallel_tool_calls": request.parallel_tool_calls,
            "reasoning": {"effort": CODEX_DEFAULT_REASONING_EFFORT.value},
            "include": ["reasoning.encrypted_content"],
        }
        if request.tools:
            payload["tools"] = [to_codex_tool_payload(tool) for tool in request.tools]
        if request.response_format is not None:
            response_format = to_codex_response_format_payload(request.response_format)
            payload["text"] = {"format": response_format}
        return payload
