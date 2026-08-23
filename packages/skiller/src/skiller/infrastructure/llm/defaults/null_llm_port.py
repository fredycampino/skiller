from skiller.domain.agent.llm.finish_type import LLMFinishType
from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.request import LLMRequest


class NullLLMPort(LLMPort[LLMRequest]):
    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            model=request.model,
            finish_type=LLMFinishType.ERROR_REQUEST_FAILED,
            error=(
                "LLM is not configured (provider='null'). "
                "Set 'llm.default_provider' in ~/.skiller/settings/agent.json "
                "or set AGENT_LLM_PROVIDER."
            ),
            error_code="provider_not_configured",
        )
