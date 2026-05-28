from skiller.domain.agent.agent_llm_provider_model import (
    AgentCodexProvider,
    AgentFakeProvider,
    AgentLLMProvider,
    AgentMiniMaxProvider,
    AgentNullProvider,
)
from skiller.domain.agent.llm_port import LLMPort
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.llm.openai_codex_responses_llm import OpenAICodexResponsesLLM
from skiller.infrastructure.llm.openai_llm import OpenAILLM

MINIMAX_BASE_URL = "https://api.minimax.io/v1"


class LLMClientFactory:
    def resolve(self, provider: AgentLLMProvider) -> LLMPort:
        if isinstance(provider, AgentNullProvider):
            return NullLLM()
        if isinstance(provider, AgentFakeProvider):
            return FakeLLM(model=provider.model)
        if isinstance(provider, AgentMiniMaxProvider):
            return self._minimax_client(provider)
        if isinstance(provider, AgentCodexProvider):
            return self._codex_client(provider)

        raise RuntimeError(f"Unsupported LLM provider: {provider!r}")

    def _minimax_client(self, provider: AgentMiniMaxProvider) -> OpenAILLM:
        return OpenAILLM(
            api_key=provider.api_key,
            base_url=MINIMAX_BASE_URL,
            timeout_seconds=provider.timeout_seconds,
        )

    def _codex_client(self, provider: AgentCodexProvider) -> OpenAICodexResponsesLLM:
        return OpenAICodexResponsesLLM(
            credentials_file=provider.credentials_file,
            timeout_seconds=provider.timeout_seconds,
        )
