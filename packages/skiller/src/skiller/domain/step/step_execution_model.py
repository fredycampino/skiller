from dataclasses import asdict, dataclass, field
from enum import Enum, StrEnum
from typing import Any, Type

from skiller.domain.action.action_model import (
    Action,
    action_from_dict,
    action_to_public_dict,
)
from skiller.domain.agent.agent_llm_provider_model import (
    AgentCodexLLMModel,
    AgentFakeLLMModel,
    AgentLLMModel,
    AgentLLMProviderType,
    AgentMiniMaxLLMModel,
    AgentNullLLMModel,
)
from skiller.domain.agent.agent_run_model import AgentStopReason
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
            "value": _to_public_value(raw) or None,
            "body_ref": body_ref if isinstance(body_ref, str) else None,
        }
        if isinstance(text_ref, str) and text_ref.strip():
            payload["text_ref"] = text_ref
        return payload


@dataclass(frozen=True)
class AssignOutput(OutputBase):
    assigned: Any = None


@dataclass(frozen=True)
class AgentUsageOutput:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    provider: AgentLLMProviderType | None
    model: AgentLLMModel | None


@dataclass(frozen=True)
class AgentFinalOutputData:
    stop_reason: AgentStopReason
    context_id: str
    final: str
    turn_count: int
    tool_call_count: int
    usage: AgentUsageOutput | None = None


@dataclass(frozen=True)
class AgentStopOutputData:
    stop_reason: AgentStopReason
    context_id: str
    message: str
    turn_count: int
    tool_call_count: int


AgentOutputData = AgentFinalOutputData | AgentStopOutputData


@dataclass(frozen=True, kw_only=True)
class AgentOutput(OutputBase):
    data: AgentOutputData


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


@dataclass(frozen=True)
class NotifyOutput(OutputBase):
    message: str = ""
    format: NotifyOutputFormat = NotifyOutputFormat.SIMPLE
    action: Action | None = None

    def to_public_dict(self) -> dict[str, Any]:
        payload = super().to_public_dict()
        value = payload.get("value")
        if isinstance(value, dict):
            if self.action is None:
                value.pop("action", None)
            else:
                value["action"] = action_to_public_dict(self.action)
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
    if step_type == StepType.AGENT:
        output_fields = _build_agent_output_fields(output_fields)
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


def _to_public_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _to_public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_public_value(item) for item in value]
    if isinstance(value, tuple):
        return [_to_public_value(item) for item in value]
    return value


def _build_agent_output_fields(output_fields: dict[str, Any]) -> dict[str, Any]:
    raw_data = output_fields.get("data")
    if not isinstance(raw_data, dict):
        raise ValueError("agent output data must be an object")
    return {"data": _build_agent_output_data(raw_data)}


def _build_agent_output_data(raw_data: dict[str, Any]) -> AgentOutputData:
    stop_reason = AgentStopReason(str(raw_data.get("stop_reason", "")))
    if stop_reason == AgentStopReason.FINAL:
        raw_usage = raw_data.get("usage")
        usage = _build_agent_usage_output(raw_usage) if raw_usage is not None else None
        return AgentFinalOutputData(
            stop_reason=stop_reason,
            context_id=str(raw_data.get("context_id", "")),
            final=str(raw_data.get("final", "")),
            turn_count=int(raw_data.get("turn_count", 0)),
            tool_call_count=int(raw_data.get("tool_call_count", 0)),
            usage=usage,
        )

    return AgentStopOutputData(
        stop_reason=stop_reason,
        context_id=str(raw_data.get("context_id", "")),
        message=str(raw_data.get("message", "")),
        turn_count=int(raw_data.get("turn_count", 0)),
        tool_call_count=int(raw_data.get("tool_call_count", 0)),
    )


def _build_agent_usage_output(raw_usage: object) -> AgentUsageOutput:
    if not isinstance(raw_usage, dict):
        raise ValueError("agent usage output must be an object")
    return AgentUsageOutput(
        prompt_tokens=_optional_int(raw_usage.get("prompt_tokens")),
        completion_tokens=_optional_int(raw_usage.get("completion_tokens")),
        total_tokens=_optional_int(raw_usage.get("total_tokens")),
        provider=_optional_provider(raw_usage.get("provider")),
        model=_optional_model(raw_usage.get("model")),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_provider(value: object) -> AgentLLMProviderType | None:
    if value is None:
        return None
    return AgentLLMProviderType(str(value))


def _optional_model(value: object) -> AgentLLMModel | None:
    if value is None:
        return None
    model_types = (
        AgentNullLLMModel,
        AgentFakeLLMModel,
        AgentMiniMaxLLMModel,
        AgentCodexLLMModel,
    )
    for model_type in model_types:
        try:
            return model_type(str(value))
        except ValueError:
            continue
    raise ValueError(f"Unsupported agent usage model: {value}")


def _build_notify_output_fields(output_fields: dict[str, Any]) -> dict[str, Any]:
    fields = dict(output_fields)
    if "format" in fields:
        fields["format"] = NotifyOutputFormat(str(fields["format"]))

    raw_action = fields.get("action")
    if raw_action is None:
        fields["action"] = None
        return fields
    if not isinstance(raw_action, dict):
        raise ValueError("notify action must be an object")

    fields["action"] = action_from_dict(raw_action)
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
