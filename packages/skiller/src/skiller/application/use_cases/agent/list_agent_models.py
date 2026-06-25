from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from skiller.domain.agent.config.model import AgentConfig
from skiller.domain.agent.config.port import (
    AgentConfigPort,
    AgentConfigProviderSource,
)
from skiller.domain.agent.llm.model import AgentLLMProviderType
from skiller.domain.agent.llm.provider_bedrock import AgentBedrockLLMModel
from skiller.domain.agent.llm.provider_lmstudio import AgentLMStudioLLMModel
from skiller.domain.agent.llm.provider_registry import (
    AgentCodexLLMModel,
    AgentLLMProvider,
    AgentMiniMaxLLMModel,
)
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.runner_port import RunnerPort


class ListAgentModelsStatus(str, Enum):
    OK = "OK"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"


@dataclass(frozen=True)
class AgentModelItem:
    name: str
    active: bool


@dataclass(frozen=True)
class AgentModelsProviderItem:
    name: str
    source: AgentConfigProviderSource
    models: tuple[AgentModelItem, ...]


@dataclass(frozen=True)
class ListAgentModelsResult:
    status: ListAgentModelsStatus
    run_id: str
    providers: tuple[AgentModelsProviderItem, ...] = ()
    error: str | None = None


_PUBLIC_PROVIDER_TYPES = (
    AgentLLMProviderType.MINIMAX,
    AgentLLMProviderType.LMSTUDIO,
    AgentLLMProviderType.CODEX,
    AgentLLMProviderType.BEDROCK,
)

_PROVIDER_MODEL_ENUMS = {
    AgentLLMProviderType.MINIMAX: AgentMiniMaxLLMModel,
    AgentLLMProviderType.LMSTUDIO: AgentLMStudioLLMModel,
    AgentLLMProviderType.CODEX: AgentCodexLLMModel,
    AgentLLMProviderType.BEDROCK: AgentBedrockLLMModel,
}


class ListAgentModelsUseCase:
    def __init__(
        self,
        *,
        run_store: RunStorePort,
        agent_config: AgentConfigPort,
        skill_runner: RunnerPort,
    ) -> None:
        self.run_store = run_store
        self.agent_config = agent_config
        self.skill_runner = skill_runner

    def execute(self, run_id: str) -> ListAgentModelsResult:
        if not run_id:
            raise RuntimeError("ListAgentModelsUseCase requires run_id")

        run = self.run_store.get_run(run_id)
        if run is None:
            return ListAgentModelsResult(
                status=ListAgentModelsStatus.RUN_NOT_FOUND,
                run_id=run_id,
                error=f"Run '{run_id}' not found",
            )

        config_path = self._resolve_agent_config_path(run.source, run.ref)
        config = self.agent_config.get_config(config_path=config_path)
        source_by_type = {
            item.provider_type: item.source
            for item in self.agent_config.list_provider_sources(config_path=config_path)
        }
        providers = self._provider_items(config=config, source_by_type=source_by_type)
        return ListAgentModelsResult(
            status=ListAgentModelsStatus.OK,
            run_id=run_id,
            providers=providers,
        )

    def _provider_items(
        self,
        *,
        config: AgentConfig,
        source_by_type: dict[AgentLLMProviderType, AgentConfigProviderSource],
    ) -> tuple[AgentModelsProviderItem, ...]:
        configured_by_type = {
            provider.type: provider for provider in config.llm.providers
        }
        return tuple(
            self._provider_item(
                provider_type=provider_type,
                configured_by_type=configured_by_type,
                default_provider=config.llm.default_provider,
                source=source_by_type.get(
                    provider_type,
                    AgentConfigProviderSource.NONE,
                ),
            )
            for provider_type in _PUBLIC_PROVIDER_TYPES
        )

    def _provider_item(
        self,
        *,
        provider_type: AgentLLMProviderType,
        configured_by_type: dict[AgentLLMProviderType, AgentLLMProvider],
        default_provider: AgentLLMProviderType,
        source: AgentConfigProviderSource,
    ) -> AgentModelsProviderItem:
        configured_provider = configured_by_type.get(provider_type)
        models = tuple(
            AgentModelItem(
                name=model.value,
                active=self._is_active_model(
                    model_name=model.value,
                    provider_type=provider_type,
                    configured_provider=configured_provider,
                    default_provider=default_provider,
                ),
            )
            for model in _PROVIDER_MODEL_ENUMS[provider_type]
        )
        return AgentModelsProviderItem(
            name=provider_type.value,
            source=source,
            models=models,
        )

    def _is_active_model(
        self,
        *,
        model_name: str,
        provider_type: AgentLLMProviderType,
        configured_provider: AgentLLMProvider | None,
        default_provider: AgentLLMProviderType,
    ) -> bool:
        if configured_provider is None:
            return False
        if provider_type != default_provider:
            return False
        return configured_provider.model.value == model_name

    def _resolve_agent_config_path(self, source: str, ref: str) -> Path | None:
        try:
            config_path = self.skill_runner.resolve_file_path(
                source,
                ref,
                "agent.json",
            )
        except (FileNotFoundError, ValueError):
            return None

        if config_path.exists():
            return config_path
        return None
