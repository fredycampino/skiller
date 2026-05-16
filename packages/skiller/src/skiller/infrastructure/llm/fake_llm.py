from skiller.domain.agent.llm_model import LLMRequest, LLMResponse

FAKE_LLM_RESPONSE_TEXT = '{"summary":"fake summary","severity":"low","next_action":"retry"}'


class FakeLLM:
    def __init__(
        self,
        *,
        response_text: str = FAKE_LLM_RESPONSE_TEXT,
        model: str = "fake-llm",
    ) -> None:
        self.response_text = response_text
        self.model = model

    def generate(self, request: LLMRequest) -> LLMResponse:
        _ = request
        return LLMResponse(
            ok=True,
            content=self.response_text,
            model=self.model,
        )
