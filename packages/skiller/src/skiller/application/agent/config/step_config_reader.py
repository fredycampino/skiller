from dataclasses import dataclass, replace

from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.domain.agent.agent_config_model import AgentConfig
from skiller.domain.agent.agent_config_port import AgentConfigPort
from skiller.domain.agent.agent_config_validation_model import AgentConfigValidation
from skiller.domain.step.run_step_model import AgentStep
from skiller.domain.tool.tool_contract import ToolConfig

AGENT_RUNTIME_SYSTEM = """You are Skiller, an assistant operating inside a step-based runtime.
Reply in the same language as the user.
Be concise and direct.
Use tools only when they genuinely help.
If more tool execution is still needed, stop and ask the user before continuing."""


@dataclass(frozen=True)
class AgentRunnerConfig:
    system: str
    task: str
    tools: tuple[ToolConfig, ...]
    config: AgentConfig


class AgentStepConfigReader:
    def __init__(
        self,
        *,
        agent_config: AgentConfigPort,
        tool_manager: ToolManager,
    ) -> None:
        self.agent_config = agent_config
        self.tool_manager = tool_manager

    def read(
        self,
        *,
        step: AgentStep,
    ) -> AgentRunnerConfig:
        config = self.agent_config.get_config()
        system = f"{AGENT_RUNTIME_SYSTEM}\n\n{step.system.strip()}"
        tool_names = list(step.tools)
        tools = self.tool_manager.get_tool_configs(tool_names)
        config = self._apply_step_overrides(config=config, step=step)

        return AgentRunnerConfig(
            system=system,
            task=step.task,
            tools=tuple(tools),
            config=config,
        )

    def validate_agent_config(self) -> AgentConfigValidation:
        return self.agent_config.validate_config()

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
