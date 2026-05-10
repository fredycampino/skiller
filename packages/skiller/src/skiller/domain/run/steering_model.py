from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass(frozen=True)
class SteeringAgentInterrupt:
    type: ClassVar[str] = "agent_interrupt"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type}


@dataclass(frozen=True)
class SteeringStepInterrupt:
    type: ClassVar[str] = "step_interrupt"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type}


@dataclass(frozen=True)
class SteeringAgentMessage:
    text: str
    type: ClassVar[str] = "agent_message"

    def __post_init__(self) -> None:
        normalized = self.text.strip()
        if not normalized:
            raise ValueError("agent_message requires non-empty text")
        object.__setattr__(self, "text", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "text": self.text,
        }


SteeringItem = SteeringAgentInterrupt | SteeringStepInterrupt | SteeringAgentMessage
SteeringItemType = (
    type[SteeringAgentInterrupt]
    | type[SteeringStepInterrupt]
    | type[SteeringAgentMessage]
)


def steering_item_from_dict(data: dict[str, Any]) -> SteeringItem:
    if not isinstance(data, dict):
        raise ValueError("steering item must be an object")

    raw_type = str(data.get("type", "")).strip()
    if raw_type == SteeringAgentInterrupt.type:
        return SteeringAgentInterrupt()
    if raw_type == SteeringStepInterrupt.type:
        return SteeringStepInterrupt()
    if raw_type == SteeringAgentMessage.type:
        return SteeringAgentMessage(text=_text_from_dict(data))

    return _legacy_steering_item_from_dict(data)


def _legacy_steering_item_from_dict(data: dict[str, Any]) -> SteeringItem:
    raw_target = str(data.get("target", "")).strip()
    raw_action = str(data.get("action", "")).strip()

    if raw_target == "agent" and raw_action in {"interrupt", "abort_turn"}:
        return SteeringAgentInterrupt()

    if raw_target == "step" and raw_action == "interrupt":
        return SteeringStepInterrupt()

    if raw_target == "agent" and raw_action in {"message", "steering_message"}:
        return SteeringAgentMessage(text=_text_from_dict(data))

    raise ValueError("unsupported steering item")


def _text_from_dict(data: dict[str, Any]) -> str:
    raw_text = data.get("text")
    if not isinstance(raw_text, str):
        raise ValueError("steering message requires text")
    return raw_text
