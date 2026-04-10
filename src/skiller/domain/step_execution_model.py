from dataclasses import asdict, dataclass, field
from typing import Any, Type

from skiller.domain.step_type import StepType


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
class SendOutput(OutputBase):
    channel: str = ""
    key: str = ""
    message: str = ""
    message_id: str | None = None


@dataclass(frozen=True)
class NotifyOutput(OutputBase):
    message: str = ""


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
class LlmPromptOutput(OutputBase):
    data: Any = None


@dataclass(frozen=True)
class McpOutput(OutputBase):
    data: dict[str, Any] | None = None


_OUTPUT_TYPES: dict[StepType, Type[OutputBase]] = {
    StepType.ASSIGN: AssignOutput,
    StepType.SEND: SendOutput,
    StepType.NOTIFY: NotifyOutput,
    StepType.SHELL: ShellOutput,
    StepType.SWITCH: SwitchOutput,
    StepType.WHEN: WhenOutput,
    StepType.WAIT_INPUT: WaitInputOutput,
    StepType.WAIT_WEBHOOK: WaitWebhookOutput,
    StepType.WAIT_CHANNEL: WaitChannelOutput,
    StepType.LLM_PROMPT: LlmPromptOutput,
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
