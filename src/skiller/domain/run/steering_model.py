from dataclasses import dataclass
from enum import Enum
from typing import Any


class SteeringTarget(str, Enum):
    AGENT = "agent"


class SteeringAction(str, Enum):
    ABORT_TURN = "abort_turn"
    STEERING_MESSAGE = "steering_message"


@dataclass(frozen=True)
class SteeringItem:
    target: SteeringTarget
    action: SteeringAction
    text: str | None = None

    def __post_init__(self) -> None:
        if self.action == SteeringAction.ABORT_TURN and self.text is not None:
            raise ValueError("abort_turn does not accept text")
        if self.action == SteeringAction.STEERING_MESSAGE:
            normalized = str(self.text or "").strip()
            if not normalized:
                raise ValueError("steering_message requires non-empty text")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SteeringItem":
        if not isinstance(data, dict):
            raise ValueError("steering item must be an object")

        raw_target = str(data.get("target", "")).strip()
        raw_action = str(data.get("action", "")).strip()
        raw_text = data.get("text")
        text = str(raw_text) if isinstance(raw_text, str) else None

        return cls(
            target=SteeringTarget(raw_target),
            action=SteeringAction(raw_action),
            text=text,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "target": self.target.value,
            "action": self.action.value,
        }
        if self.text is not None:
            data["text"] = self.text
        return data
