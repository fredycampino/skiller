from skiller.domain.agent.llm_model import LLMRequest, LLMResponse


class NullLLM:
    def generate(self, request: LLMRequest) -> LLMResponse:
        _ = request
        return LLMResponse(
            ok=False,
            error=(
                "LLM is not configured (provider='null'). "
                "Set 'llm.default_provider' in ~/.skiller/settings/agent.json "
                "or set AGENT_LLM_PROVIDER."
            ),
        )
