from typing import Any

from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.run_step_model import AgentStep
from skiller.domain.step.step_type import StepType


class AgentStepMapper:
    def to_agent(self, current_step: CurrentStep) -> AgentStep:
        if current_step.step_type != StepType.AGENT:
            raise ValueError(f"Step '{current_step.step_id}' must be an agent step")
        if "context_id" in current_step.step:
            raise ValueError(f"Step '{current_step.step_id}' does not support context_id")

        return AgentStep(
            id=current_step.step_id,
            system=self._required_string(current_step, "system"),
            task=self._required_string(current_step, "task"),
            max_turns=self._optional_positive_int(current_step, "max_turns"),
            max_tool_calls=self._optional_positive_int(current_step, "max_tool_calls"),
            tools=self._tools(current_step, current_step.step.get("tools")),
            next=self._optional_string(current_step, "next"),
        )

    def _required_string(self, current_step: CurrentStep, field: str) -> str:
        value = current_step.step.get(field)
        if value is None:
            raise ValueError(f"Step '{current_step.step_id}' requires {field}")
        if not isinstance(value, str):
            raise ValueError(f"Step '{current_step.step_id}' requires string {field}")
        if not value.strip():
            raise ValueError(f"Step '{current_step.step_id}' requires {field}")
        return value

    def _optional_string(self, current_step: CurrentStep, field: str) -> str | None:
        value = current_step.step.get(field)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"Step '{current_step.step_id}' requires string {field}")
        if not value.strip():
            raise ValueError(f"Step '{current_step.step_id}' requires non-empty {field}")
        return value

    def _optional_positive_int(self, current_step: CurrentStep, field: str) -> int | None:
        value = current_step.step.get(field)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Step '{current_step.step_id}' requires integer {field}")
        if value <= 0:
            raise ValueError(f"Step '{current_step.step_id}' requires positive {field}")
        return value

    def _tools(self, current_step: CurrentStep, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, list):
            raise ValueError(f"Step '{current_step.step_id}' requires list tools")

        tools: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Step '{current_step.step_id}' requires non-empty tool names")
            tools.append(item.strip())
        return tuple(tools)
