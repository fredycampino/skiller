from dataclasses import dataclass, replace

from skiller.domain.agent.agent_config_model import AgentConfig
from skiller.domain.agent.agent_config_port import AgentConfigPort
from skiller.domain.step.run_step_model import AgentStep

AGENT_RUNTIME_SYSTEM = """You are Skiller, an assistant operating inside a step-based runtime.
Reply in the same language as the user.
Be concise and direct.
Use tools only when they genuinely help.
If more tool execution is still needed, stop and ask the user before continuing."""


@dataclass(frozen=True)
class AgentRunnerConfig:
    system: str
    task: str
    context_id: str
    tools: tuple[str, ...]
    config: AgentConfig


class AgentStepConfigReader:
    def __init__(
        self,
        *,
        agent_config: AgentConfigPort,
    ) -> None:
        self.agent_config = agent_config

    def read(
        self,
        *,
        run_id: str,
        step: AgentStep,
    ) -> AgentRunnerConfig:
        config = self.agent_config.get_config()
        context_id = step.context_id if step.context_id is not None else run_id
        if not context_id:
            raise ValueError(f"Step '{step.id}' requires non-empty context_id")

        return AgentRunnerConfig(
            system=self._compose_system(step.system),
            task=step.task,
            context_id=context_id,
            tools=step.tools,
            config=self._apply_step_overrides(config=config, step=step),
        )

    def _compose_system(self, step_system: str) -> str:
        return f"{AGENT_RUNTIME_SYSTEM}\n\n{step_system.strip()}"

    def _apply_step_overrides(
        self,
        *,
        config: AgentConfig,
        step: AgentStep,
    ) -> AgentConfig:
        return replace(
            config,
            loop=replace(
                config.loop,
                max_turns=step.max_turns
                if step.max_turns is not None
                else config.loop.max_turns,
                max_tool_calls=step.max_tool_calls
                if step.max_tool_calls is not None
                else config.loop.max_tool_calls,
            ),
        )
