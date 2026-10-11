from dataclasses import dataclass
from enum import Enum

from skiller.domain.agent.config.agent_config_port import AgentConfigPort
from skiller.domain.agent.config.file_selection import snapshot_agent_config_file
from skiller.domain.agent.config.model import AgentConfig
from skiller.domain.agent.llm.provider_catalog import (
    LLMProviderCatalogSource,
    LLMProviderDefinition,
)
from skiller.domain.agent.llm.provider_catalog_port import LLMProviderCatalogPort
from skiller.domain.run.run_store_port import RunStorePort


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
    ) -> None:
        self.run_store = run_store
        self.agent_config = agent_config
        self.llm_provider_catalog = llm_provider_catalog

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

        config_path = self.agent_config.resolve_config_path(
            flow_dir=run.flow_path.parent,
            file_reference=snapshot_agent_config_file(run.snapshot),
        )
        config = self.agent_config.get_config(
            flow_dir=run.flow_path.parent, config_path=config_path
        )
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
