from typing import overload

from skiller.domain.agent.agent_llm_provider_model import (
    AgentCodexProvider,
    AgentFakeProvider,
    AgentLLMProvider,
    AgentMiniMaxProvider,
    AgentNullProvider,
)
from skiller.domain.agent.llm_port import LLMPort, ResolvedLLMPort
from skiller.domain.agent.llm_request import CodexLLMRequest, LLMRequest, MiniMaxLLMRequest
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentialsDatasource,
)
from skiller.infrastructure.llm.codex.codex_llm_port import CodexLLMPort
from skiller.infrastructure.llm.defaults.fake_llm_port import FakeLLMPort
from skiller.infrastructure.llm.defaults.null_llm_port import NullLLMPort
from skiller.infrastructure.llm.openai.openai_llm_port import OpenAILLMPort

MINIMAX_BASE_URL = "https://api.minimax.io/v1"


class LLMClientFactory:
    @overload
    def resolve(self, provider: AgentMiniMaxProvider) -> LLMPort[MiniMaxLLMRequest]: ...

    @overload
    def resolve(self, provider: AgentCodexProvider) -> LLMPort[CodexLLMRequest]: ...

    @overload
    def resolve(
        self,
        provider: AgentFakeProvider | AgentNullProvider,
    ) -> LLMPort[LLMRequest]: ...

    @overload
    def resolve(self, provider: AgentLLMProvider) -> ResolvedLLMPort: ...

    def resolve(self, provider: AgentLLMProvider) -> ResolvedLLMPort:
        if isinstance(provider, AgentNullProvider):
            return NullLLMPort()
        if isinstance(provider, AgentFakeProvider):
            return FakeLLMPort(model=provider.model)
        if isinstance(provider, AgentMiniMaxProvider):
            return self._minimax_client(provider)
        if isinstance(provider, AgentCodexProvider):
            return self._codex_client(provider)

        raise RuntimeError(f"Unsupported LLM provider: {provider!r}")

    def _minimax_client(self, provider: AgentMiniMaxProvider) -> OpenAILLMPort:
        return OpenAILLMPort(
            api_key=provider.api_key,
            base_url=MINIMAX_BASE_URL,
            timeout_seconds=provider.timeout_seconds,
        )

    def _codex_client(self, provider: AgentCodexProvider) -> CodexLLMPort:
        credentials_datasource = CodexCredentialsDatasource()
        return CodexLLMPort(
            credentials_file=provider.credentials_file,
            timeout_seconds=provider.timeout_seconds,
            credentials_datasource=credentials_datasource,
        )
