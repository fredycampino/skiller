from skiller.domain.agent.agent_config_model import (
    AgentLLMProviderConfig,
    AgentLLMProviderType,
)
from skiller.domain.agent.llm_port import LLMPort
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.llm.openai_codex_responses_llm import OpenAICodexResponsesLLM
from skiller.infrastructure.llm.openai_llm import OpenAILLM

MINIMAX_BASE_URL = "https://api.minimax.io/v1"


class LLMClientFactory:
    def create(self, provider: AgentLLMProviderConfig) -> LLMPort:
        if provider.provider_type == AgentLLMProviderType.NULL:
            return NullLLM()
        if provider.provider_type == AgentLLMProviderType.FAKE:
            return FakeLLM(model=provider.model)
        if provider.provider_type == AgentLLMProviderType.MINIMAX:
            return self.create_minimax(provider)
        if provider.provider_type == AgentLLMProviderType.CODEX:
            return self.create_codex(provider)

        raise RuntimeError(f"Unsupported LLM provider: {provider.provider_type.value}")

    def create_minimax(self, provider: AgentLLMProviderConfig) -> OpenAILLM:
        if provider.api_key is None:
            raise RuntimeError("MiniMax provider requires api_key")
        return OpenAILLM(
            api_key=provider.api_key,
            base_url=MINIMAX_BASE_URL,
            timeout_seconds=provider.timeout_seconds,
        )

    def create_codex(self, provider: AgentLLMProviderConfig) -> OpenAICodexResponsesLLM:
        if provider.credentials_file is None:
            raise RuntimeError("Codex provider requires credentials_file")
        return OpenAICodexResponsesLLM(
            credentials_file=provider.credentials_file,
            timeout_seconds=provider.timeout_seconds,
        )
