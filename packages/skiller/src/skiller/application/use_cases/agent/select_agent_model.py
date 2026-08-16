from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from skiller.domain.agent.config.port import AgentConfigPort
from skiller.domain.agent.llm.provider_catalog_port import LLMProviderCatalogPort
from skiller.domain.event.event_model import (
    RunModelUpdatedPayload,
    RuntimeEventDraft,
    RuntimeEventType,
)
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.runner_port import RunnerPort


class SelectAgentModelStatus(str, Enum):
    OK = "OK"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    PROVIDER_NOT_SUPPORTED = "PROVIDER_NOT_SUPPORTED"
    MODEL_NOT_SUPPORTED = "MODEL_NOT_SUPPORTED"


@dataclass(frozen=True)
class SelectAgentModelResult:
    status: SelectAgentModelStatus
    run_id: str
    provider: str
    model: str
    error: str | None = None


class SelectAgentModelUseCase:
    def __init__(
        self,
        *,
        run_store: RunStorePort,
        agent_config: AgentConfigPort,
        llm_provider_catalog: LLMProviderCatalogPort,
        runtime_events: RuntimeEventStorePort,
        skill_runner: RunnerPort,
    ) -> None:
        self.run_store = run_store
        self.agent_config = agent_config
        self.llm_provider_catalog = llm_provider_catalog
        self.runtime_events = runtime_events
        self.skill_runner = skill_runner

    def execute(
        self,
        *,
        run_id: str,
        provider: str,
        model: str,
    ) -> SelectAgentModelResult:
        if not run_id or not provider or not model:
            raise RuntimeError("SelectAgentModelUseCase requires run_id, provider, and model")

        run = self.run_store.get_run(run_id)
        if run is None:
            return SelectAgentModelResult(
                status=SelectAgentModelStatus.RUN_NOT_FOUND,
                run_id=run_id,
                provider=provider,
                model=model,
                error=f"Run '{run_id}' not found",
            )

        catalog = self.llm_provider_catalog.get_catalog()
        try:
            provider_definition = catalog.get(provider)
        except ValueError:
            return SelectAgentModelResult(
                status=SelectAgentModelStatus.PROVIDER_NOT_SUPPORTED,
                run_id=run_id,
                provider=provider,
                model=model,
                error=f"Unsupported LLM provider: {provider}",
            )

        if not provider_definition.enabled:
            return SelectAgentModelResult(
                status=SelectAgentModelStatus.PROVIDER_NOT_SUPPORTED,
                run_id=run_id,
                provider=provider,
                model=model,
                error=f"Unsupported LLM provider: {provider}",
            )

        try:
            catalog.get_model(provider_name=provider, model_name=model)
        except ValueError:
            return SelectAgentModelResult(
                status=SelectAgentModelStatus.MODEL_NOT_SUPPORTED,
                run_id=run_id,
                provider=provider,
                model=model,
                error=f"Unsupported model='{model}' for provider='{provider}'",
            )

        config_path = self._resolve_agent_config_path(run.source, run.ref)
        self.agent_config.set_model(
            provider=provider,
            model=model,
            config_path=config_path,
        )
        self.runtime_events.append_event(
            RuntimeEventDraft(
                run_id=run_id,
                type=RuntimeEventType.RUN_MODEL_UPDATED,
                payload=RunModelUpdatedPayload(
                    provider=provider,
                    model=model,
                ),
            )
        )
        return SelectAgentModelResult(
            status=SelectAgentModelStatus.OK,
            run_id=run_id,
            provider=provider,
            model=model,
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
