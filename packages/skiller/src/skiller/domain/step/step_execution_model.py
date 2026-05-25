from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Type

from skiller.domain.step.step_type import StepType


@dataclass(frozen=True)
class OutputBase:
    text: str
    text_ref: str | None = None
    body_ref: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        text = str(raw.pop("text", ""))
        text_ref = raw.pop("text_ref", None)
        body_ref = raw.pop("body_ref", None)
        payload = {
            "text": text,
            "value": raw or None,
            "body_ref": body_ref if isinstance(body_ref, str) else None,
        }
        if isinstance(text_ref, str) and text_ref.strip():
            payload["text_ref"] = text_ref
        return payload


@dataclass(frozen=True)
class AssignOutput(OutputBase):
    assigned: Any = None


@dataclass(frozen=True)
class AgentOutput(OutputBase):
    data: dict[str, Any] | None = None


@dataclass(frozen=True)
class SendOutput(OutputBase):
    channel: str = ""
    key: str = ""
    message: str = ""
    message_id: str | None = None


class NotifyOutputFormat(StrEnum):
    SIMPLE = "simple"
    STRUCTURED = "structured"
    MARKDOWN = "markdown"


class NotifyActionType(StrEnum):
    OPEN_URL = "open_url"


class NotifyActionStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"


@dataclass(frozen=True)
class NotifyOpenUrlAction:
    label: str = ""
    url: str = ""
    status: NotifyActionStatus = NotifyActionStatus.PENDING
    auto_open: bool = False


@dataclass(frozen=True)
class NotifyOutput(OutputBase):
    message: str = ""
    format: NotifyOutputFormat = NotifyOutputFormat.SIMPLE
    action_type: NotifyActionType | None = None
    action: NotifyOpenUrlAction | None = None

    def to_public_dict(self) -> dict[str, Any]:
        payload = super().to_public_dict()
        value = payload.get("value")
        if isinstance(value, dict):
            if value.get("action_type") is None:
                value.pop("action_type", None)
            if value.get("action") is None:
                value.pop("action", None)
            payload["value"] = value or None
        return payload


@dataclass(frozen=True)
class ShellOutput(OutputBase):
    ok: bool = False
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class SwitchOutput(OutputBase):
    next_step_id: str = ""


@dataclass(frozen=True)
class WhenOutput(OutputBase):
    next_step_id: str = ""


@dataclass(frozen=True)
class WaitInputOutput(OutputBase):
    prompt: str = ""
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class WaitWebhookOutput(OutputBase):
    webhook: str = ""
    key: str = ""
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class WaitChannelOutput(OutputBase):
    channel: str = ""
    key: str = ""
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class McpOutput(OutputBase):
    data: dict[str, Any] | None = None


_OUTPUT_TYPES: dict[StepType, Type[OutputBase]] = {
    StepType.AGENT: AgentOutput,
    StepType.ASSIGN: AssignOutput,
    StepType.SEND: SendOutput,
    StepType.NOTIFY: NotifyOutput,
    StepType.SHELL: ShellOutput,
    StepType.SWITCH: SwitchOutput,
    StepType.WHEN: WhenOutput,
    StepType.WAIT_INPUT: WaitInputOutput,
    StepType.WAIT_WEBHOOK: WaitWebhookOutput,
    StepType.WAIT_CHANNEL: WaitChannelOutput,
    StepType.MCP: McpOutput,
}


def _build_output(step_type: StepType, data: dict[str, Any] | None) -> OutputBase:
    output_type = _OUTPUT_TYPES[step_type]
    raw = data if isinstance(data, dict) else {}
    text = raw.get("text", "")
    text_ref = raw.get("text_ref")
    body_ref = raw.get("body_ref")
    value = raw.get("value")
    output_fields = value if isinstance(value, dict) else {}
    if step_type == StepType.NOTIFY:
        output_fields = _build_notify_output_fields(output_fields)
    return output_type(
        text=str(text),
        text_ref=(
            str(text_ref).strip()
            if isinstance(text_ref, str) and text_ref.strip()
            else None
        ),
        body_ref=(
            str(body_ref).strip()
            if isinstance(body_ref, str) and body_ref.strip()
            else None
        ),
        **output_fields,
    )


def _build_notify_output_fields(output_fields: dict[str, Any]) -> dict[str, Any]:
    fields = dict(output_fields)
    if "format" in fields:
        fields["format"] = NotifyOutputFormat(str(fields["format"]))

    if "action_type" in fields and fields["action_type"] is not None:
        fields["action_type"] = NotifyActionType(str(fields["action_type"]))

    if fields.get("action_type") == NotifyActionType.OPEN_URL:
        raw_action = fields.get("action")
        action = raw_action if isinstance(raw_action, dict) else {}
        raw_auto_open = action.get("auto_open", False)
        if not isinstance(raw_auto_open, bool):
            raise ValueError("notify action auto_open must be boolean")
        fields["action"] = NotifyOpenUrlAction(
            label=str(action.get("label", "")),
            url=str(action.get("url", "")),
            status=NotifyActionStatus(
                str(action.get("status", NotifyActionStatus.PENDING.value))
            ),
            auto_open=raw_auto_open,
        )
        return fields

    fields["action_type"] = None
    fields["action"] = None
    return fields


@dataclass(frozen=True)
class StepExecution:
    step_type: StepType
    input: dict[str, Any] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)
    output: OutputBase = field(default_factory=lambda: OutputBase(text=""))

    def to_persisted_dict(self) -> dict[str, Any]:
        return {
            "step_type": self.step_type.value,
            "input": self.input,
            "evaluation": self.evaluation,
            "output": self.output.to_public_dict(),
        }

    def to_public_output_dict(self) -> dict[str, Any]:
        return self.output.to_public_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepExecution":
        raw = data if isinstance(data, dict) else {}
        step_type = StepType(str(raw.get("step_type", "")))
        raw_input = raw.get("input")
        raw_evaluation = raw.get("evaluation")
        return cls(
            step_type=step_type,
            input=raw_input if isinstance(raw_input, dict) else {},
            evaluation=raw_evaluation if isinstance(raw_evaluation, dict) else {},
            output=_build_output(step_type, raw.get("output")),
        )
