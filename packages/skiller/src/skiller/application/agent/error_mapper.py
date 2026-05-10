from skiller.domain.agent.llm_model import LLMResponse


class AgentErrorMapper:
    def llm_request(self, *, agent_id: str, response: LLMResponse) -> str:
        detail = self._llm_error_detail(response)
        return f"Agent '{agent_id}' LLM request failed: {detail}"

    def _llm_error_detail(self, response: LLMResponse) -> str:
        if response.error and response.error_code:
            return f"{response.error} (error_code={response.error_code})"

        if response.error:
            return response.error

        if response.error_code:
            return f"error_code={response.error_code}"

        if response.finish_reason:
            return f"finish_reason={response.finish_reason}"

        if response.model:
            return f"model={response.model} returned ok=false without error"

        return "ok=false without error"
