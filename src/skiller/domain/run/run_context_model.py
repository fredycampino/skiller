from dataclasses import dataclass, field
from typing import Any

from skiller.domain.step.step_execution_model import StepExecution


@dataclass
class RunContext:
    inputs: dict[str, Any] = field(default_factory=dict)
    step_executions: dict[str, StepExecution] = field(default_factory=dict)
    steering_messages: list[str] = field(default_factory=list)
    cancel_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RunContext":
        raw = data if isinstance(data, dict) else {}
        inputs = raw.get("inputs", {})
        raw_step_executions = raw.get("step_executions", {})
        steering_messages = raw.get("steering_messages", [])
        cancel_reason = raw.get("cancel_reason")

        step_executions: dict[str, StepExecution] = {}
        if isinstance(raw_step_executions, dict):
            for step_id, raw_execution in raw_step_executions.items():
                if not isinstance(step_id, str) or not isinstance(raw_execution, dict):
                    continue
                step_executions[step_id] = StepExecution.from_dict(raw_execution)

        return cls(
            inputs=inputs if isinstance(inputs, dict) else {},
            step_executions=step_executions,
            steering_messages=steering_messages if isinstance(steering_messages, list) else [],
            cancel_reason=cancel_reason if isinstance(cancel_reason, str) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "inputs": self.inputs,
            "step_executions": {
                step_id: execution.to_persisted_dict()
                for step_id, execution in self.step_executions.items()
            },
        }
        if self.steering_messages:
            data["steering_messages"] = self.steering_messages
        if self.cancel_reason:
            data["cancel_reason"] = self.cancel_reason
        return data
