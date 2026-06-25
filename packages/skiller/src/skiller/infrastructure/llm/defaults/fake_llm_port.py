from skiller.domain.agent.llm.model import LLMResponse
from skiller.domain.agent.llm.port import LLMPort
from skiller.domain.agent.llm.provider_registry import (
    AgentFakeLLMModel,
)
from skiller.domain.agent.llm.request import LLMRequest

FAKE_LLM_RESPONSE_TEXT = '{"summary":"fake summary","severity":"low","next_action":"retry"}'


class FakeLLMPort(LLMPort[LLMRequest]):
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
