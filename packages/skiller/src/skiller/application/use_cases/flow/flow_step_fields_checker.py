from skiller.application.use_cases.flow.flow_check_model import (
    FlowCheckError,
    ParsedFlowStep,
)
from skiller.application.use_cases.flow.flow_notify_action_checker import (
    FlowNotifyActionChecker,
)
from skiller.domain.step.step_execution_model import NotifyOutputFormat
from skiller.domain.step.step_type import StepType

_REQUIRED_FIELDS = {
    StepType.AGENT.value: (
        "system",
        "FLOW_AGENT_SYSTEM_MISSING",
        "agent step requires system",
    ),
    StepType.NOTIFY.value: (
        "message",
        "FLOW_NOTIFY_MESSAGE_MISSING",
        "notify step requires message",
    ),
    StepType.SEND.value: (
        "channel",
        "FLOW_SEND_CHANNEL_MISSING",
        "send step requires channel",
    ),
    StepType.SHELL.value: (
        "command",
        "FLOW_SHELL_COMMAND_MISSING",
        "shell step requires command",
    ),
    StepType.WAIT_INPUT.value: (
        "prompt",
        "FLOW_WAIT_INPUT_PROMPT_MISSING",
        "wait_input step requires prompt",
    ),
    StepType.WAIT_WEBHOOK.value: (
        "webhook",
        "FLOW_WAIT_WEBHOOK_WEBHOOK_MISSING",
        "wait_webhook step requires webhook",
    ),
    StepType.WAIT_CHANNEL.value: (
        "channel",
        "FLOW_WAIT_CHANNEL_CHANNEL_MISSING",
        "wait_channel step requires channel",
    ),
    StepType.MCP.value: (
        "server",
        "FLOW_MCP_SERVER_MISSING",
        "mcp step requires server",
    ),
}


class FlowStepFieldsChecker:
    def __init__(self) -> None:
        self.notify_action_checker = FlowNotifyActionChecker()

    def check(
        self,
        *,
        steps: list[ParsedFlowStep],
        errors: list[FlowCheckError],
    ) -> None:
        for step in steps:
            self._check_required_fields(step=step, errors=errors)
            self._check_step_type_fields(step=step, errors=errors)

    def _check_required_fields(
        self,
        *,
        step: ParsedFlowStep,
        errors: list[FlowCheckError],
    ) -> None:
        if step.step_type not in _REQUIRED_FIELDS:
            return

        field, code, text = _REQUIRED_FIELDS[step.step_type]
        if not str(step.body.get(field, "")).strip():
            errors.append(
                FlowCheckError(
                    code=code,
                    message=f"{code}: {text} (step={step.step_id})",
                )
            )

    def _check_step_type_fields(
        self,
        *,
        step: ParsedFlowStep,
        errors: list[FlowCheckError],
    ) -> None:
        if step.step_type == StepType.NOTIFY.value:
            self._check_notify_fields(step=step, errors=errors)

        if step.step_type == StepType.AGENT.value:
            self._check_agent_fields(step=step, errors=errors)

        if step.step_type == StepType.SEND.value:
            self._check_send_fields(step=step, errors=errors)

        if step.step_type == StepType.WAIT_WEBHOOK.value:
            self._check_wait_webhook_fields(step=step, errors=errors)

        if step.step_type == StepType.WAIT_CHANNEL.value:
            self._check_wait_channel_fields(step=step, errors=errors)

        if step.step_type == StepType.MCP.value:
            self._check_mcp_fields(step=step, errors=errors)

    def _check_notify_fields(
        self,
        *,
        step: ParsedFlowStep,
        errors: list[FlowCheckError],
    ) -> None:
        raw_format = step.body.get("format")
        if raw_format is not None:
            format_value = str(raw_format).strip()
            supported_formats = {item.value for item in NotifyOutputFormat}
            if format_value not in supported_formats:
                errors.append(
                    FlowCheckError(
                        code="FLOW_NOTIFY_FORMAT_UNSUPPORTED",
                        message="FLOW_NOTIFY_FORMAT_UNSUPPORTED: notify step format "
                        "must be simple, structured or markdown "
                        f"(step={step.step_id}, format={format_value})",
                    )
                )

        self.notify_action_checker.check(step=step, errors=errors)

    def _check_agent_fields(
        self,
        *,
        step: ParsedFlowStep,
        errors: list[FlowCheckError],
    ) -> None:
        if str(step.body.get("task", "")).strip():
            return

        errors.append(
            FlowCheckError(
                code="FLOW_AGENT_TASK_MISSING",
                message=f"FLOW_AGENT_TASK_MISSING: agent step requires task "
                f"(step={step.step_id})",
            )
        )

    def _check_send_fields(
        self,
        *,
        step: ParsedFlowStep,
        errors: list[FlowCheckError],
    ) -> None:
        if not str(step.body.get("key", "")).strip():
            errors.append(
                FlowCheckError(
                    code="FLOW_SEND_KEY_MISSING",
                    message=f"FLOW_SEND_KEY_MISSING: send step requires key "
                    f"(step={step.step_id})",
                )
            )

        if not str(step.body.get("message", "")).strip():
            errors.append(
                FlowCheckError(
                    code="FLOW_SEND_MESSAGE_MISSING",
                    message=f"FLOW_SEND_MESSAGE_MISSING: send step requires message "
                    f"(step={step.step_id})",
                )
            )

        channel = str(step.body.get("channel", "")).strip().lower()
        if channel and channel != "whatsapp":
            errors.append(
                FlowCheckError(
                    code="FLOW_SEND_CHANNEL_UNSUPPORTED",
                    message="FLOW_SEND_CHANNEL_UNSUPPORTED: send step supports only "
                    f"whatsapp (step={step.step_id}, channel={channel})",
                )
            )

    def _check_wait_webhook_fields(
        self,
        *,
        step: ParsedFlowStep,
        errors: list[FlowCheckError],
    ) -> None:
        if str(step.body.get("key", "")).strip():
            return

        errors.append(
            FlowCheckError(
                code="FLOW_WAIT_WEBHOOK_KEY_MISSING",
                message="FLOW_WAIT_WEBHOOK_KEY_MISSING: wait_webhook step requires "
                f"key (step={step.step_id})",
            )
        )

    def _check_wait_channel_fields(
        self,
        *,
        step: ParsedFlowStep,
        errors: list[FlowCheckError],
    ) -> None:
        if str(step.body.get("key", "")).strip():
            return

        errors.append(
            FlowCheckError(
                code="FLOW_WAIT_CHANNEL_KEY_MISSING",
                message="FLOW_WAIT_CHANNEL_KEY_MISSING: wait_channel step requires "
                f"key (step={step.step_id})",
            )
        )

    def _check_mcp_fields(
        self,
        *,
        step: ParsedFlowStep,
        errors: list[FlowCheckError],
    ) -> None:
        if str(step.body.get("tool", "")).strip():
            return

        errors.append(
            FlowCheckError(
                code="FLOW_MCP_TOOL_MISSING",
                message=f"FLOW_MCP_TOOL_MISSING: mcp step requires tool "
                f"(step={step.step_id})",
            )
        )
