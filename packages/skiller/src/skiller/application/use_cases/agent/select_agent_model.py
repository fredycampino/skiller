from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from skiller.domain.agent.config.port import AgentConfigPort
from skiller.domain.agent.llm.model import AgentLLMProviderType
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.runner_port import RunnerPort


class SelectAgentModelStatus(str, Enum):
    OK = "OK"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    PROVIDER_NOT_SUPPORTED = "PROVIDER_NOT_SUPPORTED"
    MODEL_NOT_SUPPORTED = "MODEL_NOT_SUPPORTED"


@dataclass(frozen=True)
class SelectAgentModelResult:
    status: SelectAgentModelStatus
    run_id: str
    provider: str
    model: str
    error: str | None = None


_SELECTABLE_PROVIDER_TYPES = {
    AgentLLMProviderType.MINIMAX,
    AgentLLMProviderType.LMSTUDIO,
    AgentLLMProviderType.CODEX,
    AgentLLMProviderType.BEDROCK,
}


class SelectAgentModelUseCase:
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

        provider_type = _provider_type(provider)
        if provider_type is None:
            return SelectAgentModelResult(
                status=SelectAgentModelStatus.PROVIDER_NOT_SUPPORTED,
                run_id=run_id,
                provider=provider,
                model=model,
                error=f"Unsupported LLM provider: {provider}",
            )

        if provider_type not in _SELECTABLE_PROVIDER_TYPES:
            return SelectAgentModelResult(
                status=SelectAgentModelStatus.PROVIDER_NOT_SUPPORTED,
                run_id=run_id,
                provider=provider,
                model=model,
                error=f"Unsupported LLM provider: {provider}",
            )

        config_path = self._resolve_agent_config_path(run.source, run.ref)
        config = self.agent_config.get_config(config_path=config_path)
        configured_provider = next(
            (
                item
                for item in config.llm.providers
                if item.type == provider_type
            ),
            None,
        )
        if configured_provider is None:
            return SelectAgentModelResult(
                status=SelectAgentModelStatus.PROVIDER_NOT_CONFIGURED,
                run_id=run_id,
                provider=provider_type.value,
                model=model,
                error=f"LLM provider is not configured: {provider_type.value}",
            )

        allowed_model_values = {item.value for item in configured_provider.models}
        if model not in allowed_model_values:
            return SelectAgentModelResult(
                status=SelectAgentModelStatus.MODEL_NOT_SUPPORTED,
                run_id=run_id,
                provider=provider,
                model=model,
                error=f"Unsupported model='{model}' for provider='{provider_type.value}'",
            )

        self.agent_config.set_model(
            provider_type=provider_type,
            model=model,
            config_path=config_path,
        )
        return SelectAgentModelResult(
            status=SelectAgentModelStatus.OK,
            run_id=run_id,
            provider=provider_type.value,
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


def _provider_type(provider: str) -> AgentLLMProviderType | None:
    try:
        return AgentLLMProviderType(provider)
    except ValueError:
        return None
