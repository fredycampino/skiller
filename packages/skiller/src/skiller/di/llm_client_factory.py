from typing import overload

from skiller.domain.agent.llm.port import LLMPort, ResolvedLLMPort
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.agent.llm.provider_lmstudio import LMStudioLLMRequest
from skiller.domain.agent.llm.provider_minimax import MiniMaxLLMRequest
from skiller.domain.agent.llm.provider_registry import (
    AgentBedrockProvider,
    AgentCodexProvider,
    AgentFakeProvider,
    AgentLLMProvider,
    AgentLMStudioProvider,
    AgentMiniMaxProvider,
    AgentNullProvider,
)
from skiller.domain.agent.llm.request import LLMRequest
from skiller.infrastructure.llm.bedrock.bedrock_llm_port import BedrockLLMPort
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentialsDatasource,
)
from skiller.infrastructure.llm.codex.codex_llm_port import CodexLLMPort
from skiller.infrastructure.llm.defaults.fake_llm_port import FakeLLMPort
from skiller.infrastructure.llm.defaults.null_llm_port import NullLLMPort
from skiller.infrastructure.llm.openai.openai_llm_port import OpenAILLMPort
from skiller.infrastructure.llm.openai.openai_mapper import DefaultOpenAIMapper

MINIMAX_BASE_URL = "https://api.minimax.io/v1"


class LLMClientFactory:
    @overload
    def resolve(self, provider: AgentMiniMaxProvider) -> LLMPort[MiniMaxLLMRequest]: ...

    @overload
    def resolve(self, provider: AgentLMStudioProvider) -> LLMPort[LMStudioLLMRequest]: ...

    @overload
    def resolve(self, provider: AgentCodexProvider) -> LLMPort[CodexLLMRequest]: ...

    @overload
    def resolve(self, provider: AgentBedrockProvider) -> LLMPort[BedrockLLMRequest]: ...

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
        if isinstance(provider, AgentLMStudioProvider):
            return self._lmstudio_client(provider)
        if isinstance(provider, AgentCodexProvider):
            return self._codex_client(provider)
        if isinstance(provider, AgentBedrockProvider):
            return self._bedrock_client(provider)

        raise RuntimeError(f"Unsupported LLM provider: {provider!r}")

    def _minimax_client(self, provider: AgentMiniMaxProvider) -> OpenAILLMPort:
        return OpenAILLMPort(
            api_key=provider.api_key,
            base_url=MINIMAX_BASE_URL,
            timeout_seconds=provider.timeout_seconds,
            mapper=DefaultOpenAIMapper(extra_body={"reasoning_split": True}),
        )

    def _lmstudio_client(self, provider: AgentLMStudioProvider) -> OpenAILLMPort:
        return OpenAILLMPort(
            api_key=provider.api_key,
            base_url=provider.base_url,
            timeout_seconds=provider.timeout_seconds,
            mapper=DefaultOpenAIMapper(),
        )

    def _codex_client(self, provider: AgentCodexProvider) -> CodexLLMPort:
        credentials_datasource = CodexCredentialsDatasource()
        return CodexLLMPort(
            credentials_file=provider.credentials_file,
            timeout_seconds=provider.timeout_seconds,
            credentials_datasource=credentials_datasource,
        )

    def _bedrock_client(self, provider: AgentBedrockProvider) -> BedrockLLMPort:
        return BedrockLLMPort(
            profile=provider.profile,
            timeout_seconds=provider.timeout_seconds,
        )
