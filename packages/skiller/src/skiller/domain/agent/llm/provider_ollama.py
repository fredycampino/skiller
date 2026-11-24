from dataclasses import dataclass

from skiller.domain.agent.llm.provider_catalog import OllamaLLMModelDefinition
from skiller.domain.agent.llm.request import LLMRequest


@dataclass(frozen=True)
class OllamaLLMRequest(LLMRequest):
    model: OllamaLLMModelDefinition

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.model, OllamaLLMModelDefinition):
            raise TypeError("OllamaLLMRequest model must be an OllamaLLMModelDefinition")
