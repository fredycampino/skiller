from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunContext:
    inputs: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    steering_messages: list[str] = field(default_factory=list)
    cancel_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RunContext":
        raw = data if isinstance(data, dict) else {}
        inputs = raw.get("inputs", {})
        results = raw.get("results", {})
        steering_messages = raw.get("steering_messages", [])
        cancel_reason = raw.get("cancel_reason")

        return cls(
            inputs=inputs if isinstance(inputs, dict) else {},
            results=results if isinstance(results, dict) else {},
            steering_messages=steering_messages if isinstance(steering_messages, list) else [],
            cancel_reason=cancel_reason if isinstance(cancel_reason, str) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "inputs": self.inputs,
            "results": self.results,
        }
        if self.steering_messages:
            data["steering_messages"] = self.steering_messages
        if self.cancel_reason:
            data["cancel_reason"] = self.cancel_reason
        return data
