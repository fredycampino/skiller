from dataclasses import dataclass, replace
from pathlib import Path

from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.domain.agent.config.model import AgentConfig
from skiller.domain.agent.config.port import AgentConfigPort
from skiller.domain.agent.config.validation import (
    AgentConfigValidation,
    AgentConfigValidationErrorCode,
)
from skiller.domain.agent.context.model import AgentContextMetrics
from skiller.domain.agent.llm.provider_catalog import (
    LLMModelDefinition,
    LLMProviderDefinition,
)
from skiller.domain.agent.llm.provider_catalog_port import LLMProviderCatalogPort
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.run_step_model import AgentStep
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.tool.tool_contract import ToolDefinition

AGENT_RUNTIME_SYSTEM = (
    "You are a friendly assistant operating inside a runtime agent harness "
    "step-based called Skiller.\n"
    "Reply in the same standard language as the user, for example standard Spanish "
    "when the user writes in Spanish.\n"
    "Be concise and direct, avoid verbose.\n"
    "Use tools only when they genuinely help.\n"
    "The feedback of harness go labeled as [Skiller]"
)


@dataclass(frozen=True)
class AgentRunnerConfig:
    system: str
    task: str
    tools: tuple[ToolDefinition, ...]
    config: AgentConfig
    provider_definition: LLMProviderDefinition

    def __post_init__(self) -> None:
        if self.provider_definition.name != self.config.llm.provider:
            raise ValueError("Agent runner provider does not match agent config")
        self.model_definition()

    def model_definition(self) -> LLMModelDefinition:
        selected_model = self.config.llm.model
        for model in self.provider_definition.models:
            if model.model == selected_model:
                return model
        raise ValueError(
            f"Unsupported model='{selected_model}' for provider='{self.provider_definition.name}'"
        )

    def context_metrics(self) -> AgentContextMetrics:
        model = self.model_definition()
        return self.config.context.metrics(
            model_context_window_tokens=model.context_window_tokens,
        )


class AgentStepConfigReader:
    def __init__(
        self,
        *,
        agent_config: AgentConfigPort,
        llm_provider_catalog: LLMProviderCatalogPort,
        run_store: RunStorePort,
        skill_runner: RunnerPort,
        tool_manager: ToolManager,
    ) -> None:
        self.agent_config = agent_config
        self.llm_provider_catalog = llm_provider_catalog
        self.run_store = run_store
        self.skill_runner = skill_runner
        self.tool_manager = tool_manager

    def read(
        self,
        *,
        step: AgentStep,
        current_step: CurrentStep,
    ) -> AgentRunnerConfig:
        config_path = self._resolve_agent_config_path(current_step)
        config = self.agent_config.get_config(config_path=config_path)
        catalog = self.llm_provider_catalog.get_catalog()
        provider_definition = catalog.get(config.llm.provider)
        catalog.get_model(
            provider_name=config.llm.provider,
            model_name=config.llm.model,
        )
        tool_names = list(step.tools)
        tools = self.tool_manager.get_tool_definitions(tool_names)
        config = self._apply_step_overrides(config=config, step=step)

        return AgentRunnerConfig(
            system=self._build_system_prompt(step=step, tools=tools),
            task=step.task,
            tools=tuple(tools),
            config=config,
            provider_definition=provider_definition,
        )

    def _build_system_prompt(
        self,
        *,
        step: AgentStep,
        tools: list[ToolDefinition],
    ) -> str:
        parts = [AGENT_RUNTIME_SYSTEM]
        tool_section = self._build_tools_section(tools)
        if tool_section:
            parts.append(tool_section)
        step_system = step.system.strip()
        if step_system:
            parts.append(step_system)
        return "\n\n".join(parts)

    def _build_tools_section(self, tools: list[ToolDefinition]) -> str:
        if not tools:
            return ""
        lines = ["## Available Tools", ""]
        for tool in tools:
            schema = tool.schema().value
            lines.append(f"- **{tool.name}**: {tool.description}")
            params = list(schema.get("properties", {}).keys())
            if params:
                lines.append(f"  Parameters: {', '.join(params)}")
        return "\n".join(lines)

    def validate_agent_config(self, *, current_step: CurrentStep) -> AgentConfigValidation:
        config_path = self._resolve_agent_config_path(current_step)
        validation = self.agent_config.validate_config(config_path=config_path)
        if not validation.ok:
            return validation

        try:
            config = self.agent_config.get_config(config_path=config_path)
            catalog = self.llm_provider_catalog.get_catalog()
            catalog.get_model(
                provider_name=config.llm.provider,
                model_name=config.llm.model,
            )
        except ValueError as exc:
            message = str(exc)
            error = AgentConfigValidationErrorCode.INVALID_SCHEMA
            if message.startswith("Unsupported LLM provider:"):
                error = AgentConfigValidationErrorCode.DEFAULT_PROVIDER_NOT_FOUND
            if message.startswith("Unsupported model="):
                error = AgentConfigValidationErrorCode.PROVIDER_MODEL_UNSUPPORTED
            return AgentConfigValidation.invalid(error=error, message=message)

        return AgentConfigValidation.valid()

    def _resolve_agent_config_path(self, current_step: CurrentStep) -> Path | None:
        run = self.run_store.get_run(current_step.run_id)
        if run is None:
            raise ValueError(f"Run '{current_step.run_id}' not found")

        try:
            config_path = self.skill_runner.resolve_file_path(
                run.source,
                run.ref,
                "agent.json",
            )
        except (FileNotFoundError, ValueError):
            return None

        if config_path.exists():
            return config_path
        return None

    def _apply_step_overrides(
        self,
        *,
        config: AgentConfig,
        step: AgentStep,
    ) -> AgentConfig:
        max_turns = config.loop.max_turns
        if step.max_turns is not None:
            max_turns = step.max_turns

        max_tool_calls = config.loop.max_tool_calls
        if step.max_tool_calls is not None:
            max_tool_calls = step.max_tool_calls

        loop = replace(
            config.loop,
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
        )

        return replace(
            config,
            loop=loop,
        )
