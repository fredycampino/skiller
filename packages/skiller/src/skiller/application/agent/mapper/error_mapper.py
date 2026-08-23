import json

from skiller.domain.agent.llm.model import LLMResponse, LLMUsage


class AgentErrorMapper:
    def llm_request(self, *, agent_id: str, response: LLMResponse) -> str:
        detail = self._llm_error_detail(response)
        return f"Agent '{agent_id}' LLM request failed: {detail}"

    def invalid_final_message(self, *, agent_id: str, response: LLMResponse) -> str:
        payload = _response_payload(response)
        return (
            f"Agent step '{agent_id}' returned no final answer: "
            f"{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
        )

    def _llm_error_detail(self, response: LLMResponse) -> str:
        if response.error and response.error_code:
            return f"{response.error} (error_code={response.error_code})"

        if response.error:
            return response.error

        if response.error_code:
            return f"error_code={response.error_code}"

        return f"finish_type={response.finish_type.value}"


def _response_payload(response: LLMResponse) -> dict[str, object]:
    return {
        "model": response.model.value,
        "finish_type": response.finish_type.value,
        "content": response.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "name": tool_call.function.name,
                "arguments_json": tool_call.function.arguments_json,
            }
            for tool_call in response.tool_calls
        ],
        "usage": _usage_payload(response.usage),
        "error": response.error,
        "error_code": response.error_code,
    }


def _usage_payload(usage: LLMUsage | None) -> dict[str, object] | None:
    if usage is None:
        return None
    return {
        "prompt_tokens": usage.prompt_tokens,
        "estimated_system_tokens": usage.estimated_system_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "provider": usage.provider,
        "model": usage.model,
    }
