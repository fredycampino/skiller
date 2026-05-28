from skiller.domain.agent.agent_llm_provider_model import (
    AgentFakeLLMModel,
)
from skiller.domain.agent.llm_model import LLMRequest, LLMResponse

FAKE_LLM_RESPONSE_TEXT = '{"summary":"fake summary","severity":"low","next_action":"retry"}'


class FakeLLM:
    def __init__(
        self,
        *,
        response_text: str = FAKE_LLM_RESPONSE_TEXT,
        model: AgentFakeLLMModel = AgentFakeLLMModel.MODEL1,
    ) -> None:
        self.response_text = response_text
        self.model = model

    def generate(self, request: LLMRequest) -> LLMResponse:
        _ = request
        return LLMResponse(
            ok=True,
            model=self.model,
            content=self.response_text,
        )
