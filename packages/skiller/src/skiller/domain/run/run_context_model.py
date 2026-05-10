from dataclasses import dataclass, field
from typing import Any

from skiller.domain.run.steering_model import (
    SteeringAgentMessage,
    SteeringItem,
    steering_item_from_dict,
)
from skiller.domain.step.step_execution_model import StepExecution


@dataclass
class RunContext:
    inputs: dict[str, Any] = field(default_factory=dict)
    step_executions: dict[str, StepExecution] = field(default_factory=dict)
    steering_queue: list[SteeringItem] = field(default_factory=list)
    cancel_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RunContext":
        raw = data if isinstance(data, dict) else {}
        inputs = raw.get("inputs", {})
        raw_step_executions = raw.get("step_executions", {})
        raw_steering_queue = raw.get("steering_queue", raw.get("steering_messages", []))
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
            steering_queue=_build_steering_queue(raw_steering_queue),
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
        if self.steering_queue:
            data["steering_queue"] = [item.to_dict() for item in self.steering_queue]
        if self.cancel_reason:
            data["cancel_reason"] = self.cancel_reason
        return data


def _build_steering_queue(raw: Any) -> list[SteeringItem]:
    if not isinstance(raw, list):
        return []

    queue: list[SteeringItem] = []
    for item in raw:
        try:
            if isinstance(item, dict):
                queue.append(steering_item_from_dict(item))
                continue
            if isinstance(item, str) and item.strip():
                queue.append(SteeringAgentMessage(text=item))
        except ValueError:
            continue
    return queue
