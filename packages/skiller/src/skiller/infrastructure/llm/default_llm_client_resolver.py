from typing import overload

from skiller.domain.agent.llm.port import LLMPort, ResolvedLLMPort
from skiller.domain.agent.llm.provider_bedrock import BedrockLLMRequest
from skiller.domain.agent.llm.provider_catalog import (
    BedrockLLMProviderDefinition,
    CodexLLMProviderDefinition,
    LLMProviderDefinition,
    OpenAILLMProviderDefinition,
)
from skiller.domain.agent.llm.provider_codex import CodexLLMRequest
from skiller.domain.agent.llm.request import OpenAILLMRequest
from skiller.infrastructure.llm.bedrock.bedrock_mapper import BedrockMapper
from skiller.infrastructure.llm.bedrock.bedrock_request_logger import (
    BedrockFileLLMRequestLogger,
)
from skiller.infrastructure.llm.bedrock.collect_converse_response import (
    CollectConverseResponse,
)
from skiller.infrastructure.llm.bedrock.converse_llm_port import (
    ConverseLLMPort,
)
from skiller.infrastructure.llm.bedrock.converse_mapper import (
    ConverseMapper,
)
from skiller.infrastructure.llm.codex.codex_credentials_datasource import (
    CodexCredentialsDatasource,
)
from skiller.infrastructure.llm.codex.codex_mapper import CodexMapper
from skiller.infrastructure.llm.codex.codex_model_capabilities import (
    CodexModelCapabilitiesResolver,
)
from skiller.infrastructure.llm.codex.codex_request_logger import (
    CodexFileLLMRequestLogger,
)
from skiller.infrastructure.llm.codex.codex_turn_session import CodexTurnSessionManager
from skiller.infrastructure.llm.codex.collect_codex_response import CollectCodexResponse
from skiller.infrastructure.llm.codex.responses_general_mapper import (
    ResponsesGeneralMapper,
)
from skiller.infrastructure.llm.codex.responses_lite_mapper import ResponsesLiteMapper
from skiller.infrastructure.llm.codex.responses_llm_port import ResponsesLLMPort
from skiller.infrastructure.llm.codex.responses_mapper import ResponsesMapper
from skiller.infrastructure.llm.mapper.llm_usage_mapper import DefaultLLMUsageMapper
from skiller.infrastructure.llm.openai.openai_api_key_datasource import (
    OpenAIApiKeyDatasource,
)
from skiller.infrastructure.llm.openai.openai_llm_port import OpenAILLMPort
from skiller.infrastructure.llm.openai.openai_mapper import OpenAIMapper
from skiller.infrastructure.llm.openai.openai_request_logger import (
    OpenAIFileLLMRequestLogger,
)


class DefaultLLMClientResolver:
    def __init__(self, *, api_key_datasource: OpenAIApiKeyDatasource) -> None:
        self.api_key_datasource = api_key_datasource

    @overload
    def resolve(self, provider: OpenAILLMProviderDefinition) -> LLMPort[OpenAILLMRequest]: ...

    @overload
    def resolve(self, provider: CodexLLMProviderDefinition) -> LLMPort[CodexLLMRequest]: ...

    @overload
    def resolve(self, provider: BedrockLLMProviderDefinition) -> LLMPort[BedrockLLMRequest]: ...

    @overload
    def resolve(self, provider: LLMProviderDefinition) -> ResolvedLLMPort: ...

    def resolve(self, provider: LLMProviderDefinition) -> ResolvedLLMPort:
        if isinstance(provider, OpenAILLMProviderDefinition):
            api_key = self.api_key_datasource.get_api_key(provider.api_key_source)
            return OpenAILLMPort(
                api_key=api_key,
                base_url=provider.base_url,
                timeout_seconds=provider.timeout_seconds,
                mapper=OpenAIMapper(
                    usage_mapper=DefaultLLMUsageMapper(),
                    extra_body=provider.options or None,
                ),
                request_logger=OpenAIFileLLMRequestLogger(),
            )
        if isinstance(provider, CodexLLMProviderDefinition):
            usage_mapper = DefaultLLMUsageMapper()
            request_mapper = CodexMapper(
                capabilities_resolver=CodexModelCapabilitiesResolver(),
                responses_mapper=ResponsesGeneralMapper(),
                responses_lite_mapper=ResponsesLiteMapper(),
            )
            return ResponsesLLMPort(
                credentials_file=provider.credentials_file,
                timeout_seconds=provider.timeout_seconds,
                credentials_datasource=CodexCredentialsDatasource(),
                request_logger=CodexFileLLMRequestLogger(),
                request_mapper=request_mapper,
                response_mapper=ResponsesMapper(usage_mapper=usage_mapper),
                collector=CollectCodexResponse(),
                turn_session_manager=CodexTurnSessionManager(),
            )
        if isinstance(provider, BedrockLLMProviderDefinition):
            return ConverseLLMPort(
                profile=provider.profile,
                timeout_seconds=provider.timeout_seconds,
                request_logger=BedrockFileLLMRequestLogger(),
                request_mapper=BedrockMapper(),
                response_mapper=ConverseMapper(usage_mapper=DefaultLLMUsageMapper()),
                collector=CollectConverseResponse(),
            )
        raise RuntimeError(f"Unsupported LLM adapter: {provider.adapter}")
