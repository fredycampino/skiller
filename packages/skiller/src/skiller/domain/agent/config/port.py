from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from skiller.domain.agent.config.model import AgentConfig
from skiller.domain.agent.config.validation import AgentConfigValidation
from skiller.domain.agent.llm.model import AgentLLMProviderType


class AgentConfigProviderSource(str, Enum):
    GLOBAL = "global"
    LOCAL = "local"
    ENV = "env"
    NONE = "none"


@dataclass(frozen=True)
class AgentConfigProviderSourceItem:
    provider_type: AgentLLMProviderType
    source: AgentConfigProviderSource


class AgentConfigPort(Protocol):
    def get_config(self, *, config_path: Path | None = None) -> AgentConfig:
        raise NotImplementedError

    def validate_config(self, *, config_path: Path | None = None) -> AgentConfigValidation:
        raise NotImplementedError

    def list_provider_sources(
        self,
        *,
        config_path: Path | None = None,
    ) -> tuple[AgentConfigProviderSourceItem, ...]:
        raise NotImplementedError

    def set_model(
        self,
        *,
        provider_type: AgentLLMProviderType,
        model: str,
        config_path: Path | None = None,
    ) -> None:
        raise NotImplementedError
