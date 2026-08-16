from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from skiller.domain.agent.config.model import AgentConfig
from skiller.domain.agent.config.port import AgentConfigPort
from skiller.domain.agent.llm.provider_catalog import (
    LLMProviderCatalogSource,
    LLMProviderDefinition,
)
from skiller.domain.agent.llm.provider_catalog_port import LLMProviderCatalogPort
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
    source: LLMProviderCatalogSource
    models: tuple[AgentModelItem, ...]


@dataclass(frozen=True)
class ListAgentModelsResult:
    status: ListAgentModelsStatus
    run_id: str
    providers: tuple[AgentModelsProviderItem, ...] = ()
    error: str | None = None


class ListAgentModelsUseCase:
    def __init__(
        self,
        *,
        run_store: RunStorePort,
        agent_config: AgentConfigPort,
        llm_provider_catalog: LLMProviderCatalogPort,
        skill_runner: RunnerPort,
    ) -> None:
        self.run_store = run_store
        self.agent_config = agent_config
        self.llm_provider_catalog = llm_provider_catalog
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
        catalog = self.llm_provider_catalog.get_catalog()
        providers = tuple(
            self._provider_item(
                provider=provider,
                config=config,
                source=catalog.source_for(provider.name),
            )
            for provider in catalog.providers
            if provider.enabled
        )
        return ListAgentModelsResult(
            status=ListAgentModelsStatus.OK,
            run_id=run_id,
            providers=providers,
        )

    def _provider_item(
        self,
        *,
        provider: LLMProviderDefinition,
        config: AgentConfig,
        source: LLMProviderCatalogSource,
    ) -> AgentModelsProviderItem:
        models = tuple(
            AgentModelItem(
                name=model.model,
                active=(provider.name == config.llm.provider and model.model == config.llm.model),
            )
            for model in provider.models
        )
        return AgentModelsProviderItem(
            name=provider.name,
            source=source,
            models=models,
        )

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
