from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.llm.provider_catalog import (
    LLMApiKeySource,
    LLMApiKeySourceType,
)


class OpenAIApiKeyDatasource:
    def __init__(self, *, env: Mapping[str, str]) -> None:
        self.env = env

    def get_api_key(self, source: LLMApiKeySource | None) -> str:
        if source is None:
            return ""
        if source.type == LLMApiKeySourceType.VALUE:
            return source.value
        if source.type == LLMApiKeySourceType.ENV:
            value = self.env.get(source.value)
            if value is None:
                raise ValueError(f"Missing LLM API key environment variable: {source.value}")
            return value
        if source.type == LLMApiKeySourceType.FILE:
            path = Path(source.value).expanduser()
            if not path.exists():
                raise ValueError(f"Missing LLM API key file: {path}")
            return path.read_text(encoding="utf-8").strip()
        raise ValueError(f"Unsupported LLM API key source: {source.type}")
