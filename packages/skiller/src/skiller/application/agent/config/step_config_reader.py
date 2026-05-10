from dataclasses import dataclass
from typing import Any

AGENT_RUNTIME_SYSTEM = """You are Skiller, an assistant operating inside a step-based runtime.
Reply in the same language as the user.
Be concise and direct.
Use tools only when they genuinely help.
If more tool execution is still needed, stop and ask the user before continuing."""


@dataclass(frozen=True)
class AgentStepConfig:
    system: str
    task: str
    context_id: str
    max_turns: int
    tools: list[str]
    max_tool_calls: int = 1


class AgentStepConfigReader:
    def __init__(
        self,
        *,
        default_max_turns: int = 1,
        default_max_tool_calls: int = 1,
    ) -> None:
        self.default_max_turns = default_max_turns
        self.default_max_tool_calls = default_max_tool_calls

    def read(
        self,
        *,
        step_id: str,
        run_id: str,
        step: dict[str, Any],
    ) -> AgentStepConfig:
        raw_system = step.get("system")
        if raw_system is None:
            raise ValueError(f"Step '{step_id}' requires system")
        if not isinstance(raw_system, str):
            raise ValueError(f"Step '{step_id}' requires string system")
        system = raw_system
        if not system.strip():
            raise ValueError(f"Step '{step_id}' requires system")

        raw_task = step.get("task")
        if raw_task is None:
            raise ValueError(f"Step '{step_id}' requires task")
        if not isinstance(raw_task, str):
            raise ValueError(f"Step '{step_id}' requires string task")
        task = raw_task
        if not task.strip():
            raise ValueError(f"Step '{step_id}' requires task")

        raw_context_id = step.get("context_id")
        context_id = str(raw_context_id).strip() if raw_context_id is not None else run_id
        if not context_id:
            raise ValueError(f"Step '{step_id}' requires non-empty context_id")

        return AgentStepConfig(
            system=self._compose_system(system),
            task=task,
            context_id=context_id,
            max_turns=self._parse_max_turns(step_id=step_id, value=step.get("max_turns")),
            tools=self._parse_tools(step_id=step_id, value=step.get("tools")),
            max_tool_calls=self.default_max_tool_calls,
        )

    def _parse_max_turns(self, *, step_id: str, value: object) -> int:
        if value is None:
            return self.default_max_turns
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Step '{step_id}' requires integer max_turns")
        if value <= 0:
            raise ValueError(f"Step '{step_id}' requires positive max_turns")
        return value

    def _parse_tools(self, *, step_id: str, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"Step '{step_id}' requires list tools")

        tools: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Step '{step_id}' requires non-empty tool names")
            tools.append(item.strip())
        return tools

    def _compose_system(self, step_system: str) -> str:
        return f"{AGENT_RUNTIME_SYSTEM}\n\n{step_system.strip()}"
