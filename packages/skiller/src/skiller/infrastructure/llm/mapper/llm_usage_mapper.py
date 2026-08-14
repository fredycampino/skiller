from dataclasses import dataclass
from typing import Protocol

from skiller.domain.agent.llm.model import LLMSystemMessage, LLMUsage
from skiller.domain.agent.llm.request import LLMRequest


@dataclass(frozen=True)
class LLMProviderUsage:
    prompt_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None


class LLMUsageMapper(Protocol):
    def to_usage(
        self,
        provider_usage: LLMProviderUsage | None,
        *,
        request: LLMRequest,
    ) -> LLMUsage | None: ...


@dataclass(frozen=True)
class DefaultLLMUsageMapper(LLMUsageMapper):
    def to_usage(
        self,
        provider_usage: LLMProviderUsage | None,
        *,
        request: LLMRequest,
    ) -> LLMUsage | None:
        if provider_usage is None:
            return None

        total_chars = sum(len(message.content or "") for message in request.messages)
        system_chars = sum(
            len(message.content)
            for message in request.messages
            if isinstance(message, LLMSystemMessage)
        )
        estimated_system_tokens = None
        if provider_usage.prompt_tokens is not None and total_chars > 0:
            estimated_system_tokens = round(
                provider_usage.prompt_tokens * system_chars / total_chars
            )

        return LLMUsage(
            provider=None,
            model=None,
            prompt_tokens=provider_usage.prompt_tokens,
            estimated_system_tokens=estimated_system_tokens,
            output_tokens=provider_usage.output_tokens,
            total_tokens=provider_usage.total_tokens,
            cache_read_tokens=provider_usage.cache_read_tokens,
            cache_write_tokens=provider_usage.cache_write_tokens,
        )
