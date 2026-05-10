from typing import Protocol

from skiller.domain.agent.llm_model import LLMRequest, LLMResponse


class LLMPort(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse: ...
