from dataclasses import dataclass, replace
from pathlib import Path

from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.domain.agent.agent_config_model import AgentConfig
from skiller.domain.agent.agent_config_port import AgentConfigPort
from skiller.domain.agent.agent_config_validation_model import AgentConfigValidation
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.run_step_model import AgentStep
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.tool.tool_contract import ToolDefinition

AGENT_RUNTIME_SYSTEM = """You are Skiller, an assistant operating inside a step-based runtime.
Reply in the same language as the user.
Be concise and direct.
Use tools only when they genuinely help.
If more tool execution is still needed, stop and ask the user before continuing."""


@dataclass(frozen=True)
class AgentRunnerConfig:
    system: str
    task: str
    tools: tuple[ToolDefinition, ...]
    config: AgentConfig


class AgentStepConfigReader:
    def __init__(
        self,
        *,
        agent_config: AgentConfigPort,
        run_store: RunStorePort,
        skill_runner: RunnerPort,
        tool_manager: ToolManager,
    ) -> None:
        self.agent_config = agent_config
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
        system = f"{AGENT_RUNTIME_SYSTEM}\n\n{step.system.strip()}"
        tool_names = list(step.tools)
        tools = self.tool_manager.get_tool_definitions(tool_names)
        config = self._apply_step_overrides(config=config, step=step)

        return AgentRunnerConfig(
            system=system,
            task=step.task,
            tools=tuple(tools),
            config=config,
        )

    def validate_agent_config(self, *, current_step: CurrentStep) -> AgentConfigValidation:
        config_path = self._resolve_agent_config_path(current_step)
        return self.agent_config.validate_config(config_path=config_path)

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
