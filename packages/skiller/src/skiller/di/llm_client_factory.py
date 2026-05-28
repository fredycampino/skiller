from skiller.domain.agent.agent_llm_provider_model import (
    AgentLLMProvider,
    AgentLLMProviderType,
)
from skiller.domain.agent.llm_port import LLMPort
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.llm.openai_codex_responses_llm import OpenAICodexResponsesLLM
from skiller.infrastructure.llm.openai_llm import OpenAILLM

MINIMAX_BASE_URL = "https://api.minimax.io/v1"


class LLMClientFactory:
    def resolve(self, provider: AgentLLMProvider) -> LLMPort:
        if provider.type == AgentLLMProviderType.NULL:
            return NullLLM()
        if provider.type == AgentLLMProviderType.FAKE:
            return FakeLLM(model=provider.model)
        if provider.type == AgentLLMProviderType.MINIMAX:
            return self._minimax_client(provider)
        if provider.type == AgentLLMProviderType.CODEX:
            return self._codex_client(provider)

        raise RuntimeError(f"Unsupported LLM provider: {provider.type.value}")

    def _minimax_client(self, provider: AgentLLMProvider) -> OpenAILLM:
        if provider.api_key is None:
            raise RuntimeError("MiniMax provider requires api_key")
        return OpenAILLM(
            api_key=provider.api_key,
            base_url=MINIMAX_BASE_URL,
            timeout_seconds=provider.timeout_seconds,
        )

    def _codex_client(self, provider: AgentLLMProvider) -> OpenAICodexResponsesLLM:
        if provider.credentials_file is None:
            raise RuntimeError("Codex provider requires credentials_file")
        return OpenAICodexResponsesLLM(
            credentials_file=provider.credentials_file,
            timeout_seconds=provider.timeout_seconds,
        )
