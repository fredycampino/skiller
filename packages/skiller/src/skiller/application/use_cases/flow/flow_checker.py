from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.domain.action.action_model import ActionType
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.step.step_execution_model import NotifyOutputFormat
from skiller.domain.step.step_type import StepType

_TEMPLATE_RE = re.compile(r"{{\s*([^}]+?)\s*}}")
_FULL_TEMPLATE_RE = re.compile(r"^\s*{{\s*([^}]+?)\s*}}\s*$")
_OUTPUT_VALUE_CALL_RE = re.compile(r'^output_value\((.*)\)((?:\.[A-Za-z_][A-Za-z0-9_]*)*)$')
_STRING_LITERAL_RE = re.compile(r'^(["\'])([^"\']+)\1$')
_UNSUPPORTED_HELPER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*\(")


class FlowCheckStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(frozen=True)
class FlowCheckError:
    code: str
    message: str


@dataclass(frozen=True)
class FlowCheckResult:
    status: FlowCheckStatus
    errors: list[FlowCheckError]


@dataclass(frozen=True)
class _ParsedStep:
    index: int
    step_id: str
    step_type: str
    body: dict[str, Any]


class FlowCheckerUseCase:
    def __init__(self, runner: RunnerPort) -> None:
        self.runner = runner

    def execute(
        self,
        flow_ref: str,
        *,
        flow_source: str,
    ) -> FlowCheckResult:
        raw_flow = self.runner.load(flow_source, flow_ref)
        errors: list[FlowCheckError] = []

        if not isinstance(raw_flow, dict):
            return self._invalid(
                errors,
                "FLOW_FORMAT_INVALID",
                "FLOW_FORMAT_INVALID: flow must be an object",
            )

        name = str(raw_flow.get("name", "")).strip()
        if not name:
            self._add(
                errors,
                "FLOW_NAME_MISSING",
                "FLOW_NAME_MISSING: flow requires non-empty name",
            )

        start = str(raw_flow.get("start", "")).strip()
        if not start:
            self._add(
                errors,
                "FLOW_START_MISSING",
                "FLOW_START_MISSING: flow requires non-empty start",
            )

        if "steps" not in raw_flow:
            self._add(errors, "FLOW_STEPS_MISSING", "FLOW_STEPS_MISSING: flow requires steps")
            return self._result(errors)

        raw_steps = raw_flow.get("steps")
        if not isinstance(raw_steps, list):
            self._add(
                errors,
                "FLOW_STEPS_INVALID",
                "FLOW_STEPS_INVALID: flow steps must be a list",
            )
            return self._result(errors)
        if not raw_steps:
            self._add(
                errors,
                "FLOW_STEPS_EMPTY",
                "FLOW_STEPS_EMPTY: flow requires at least one step",
            )
            return self._result(errors)

        parsed_steps = self._collect_steps(raw_steps, errors)
        step_ids = {step.step_id for step in parsed_steps}

        if start and start not in step_ids:
            self._add(
                errors,
                "FLOW_START_STEP_NOT_FOUND",
                f"FLOW_START_STEP_NOT_FOUND: start references unknown step_id (start={start})",
            )

        for step in parsed_steps:
            self._check_step_targets(step, step_ids, errors)
            self._check_required_fields(step, errors)
            self._check_templates(step, step_ids, parsed_steps, errors)

        return self._result(errors)

    def _collect_steps(
        self,
        raw_steps: list[Any],
        errors: list[FlowCheckError],
    ) -> list[_ParsedStep]:
        parsed_steps: list[_ParsedStep] = []
        seen_step_ids: set[str] = set()
        valid_step_types = {item.value for item in StepType}

        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, dict):
                self._add(
                    errors,
                    "FLOW_STEP_PRIMARY_HEADER_MISSING",
                    "FLOW_STEP_PRIMARY_HEADER_MISSING: step requires a primary "
                    f"header (index={index})",
                )
                continue

            primary_keys = [key for key in raw_step if key in valid_step_types]
            if not primary_keys:
                if raw_step:
                    first_key = next(iter(raw_step))
                    self._add(
                        errors,
                        "FLOW_STEP_PRIMARY_HEADER_INVALID",
                        "FLOW_STEP_PRIMARY_HEADER_INVALID: unsupported step type "
                        f"(index={index}, step_type={first_key})",
                    )
                    continue
                self._add(
                    errors,
                    "FLOW_STEP_PRIMARY_HEADER_MISSING",
                    "FLOW_STEP_PRIMARY_HEADER_MISSING: step requires a primary "
                    f"header (index={index})",
                )
                continue
            if len(primary_keys) > 1:
                self._add(
                    errors,
                    "FLOW_STEP_PRIMARY_HEADER_INVALID",
                    "FLOW_STEP_PRIMARY_HEADER_INVALID: unsupported step type "
                    f"(index={index}, step_type=multiple)",
                )
                continue

            step_type = primary_keys[0]
            step_id = str(raw_step.get(step_type, "")).strip()
            if not step_id:
                self._add(
                    errors,
                    "FLOW_STEP_ID_MISSING",
                    "FLOW_STEP_ID_MISSING: step requires non-empty step_id "
                    f"(index={index}, step_type={step_type})",
                )
                continue

            if step_id in seen_step_ids:
                self._add(
                    errors,
                    "FLOW_STEP_ID_DUPLICATED",
                    f"FLOW_STEP_ID_DUPLICATED: duplicated step_id (step_id={step_id})",
                )
                continue

            seen_step_ids.add(step_id)
            parsed_steps.append(
                _ParsedStep(
                    index=index,
                    step_id=step_id,
                    step_type=step_type,
                    body={key: value for key, value in raw_step.items() if key != step_type},
                )
            )

        return parsed_steps

    def _check_step_targets(
        self,
        step: _ParsedStep,
        step_ids: set[str],
        errors: list[FlowCheckError],
    ) -> None:
        raw_next = step.body.get("next")
        if raw_next is not None:
            next_step_id = str(raw_next).strip()
            if not next_step_id:
                self._add(
                    errors,
                    "FLOW_STEP_NEXT_EMPTY",
                    f"FLOW_STEP_NEXT_EMPTY: next requires non-empty target (step={step.step_id})",
                )
            elif next_step_id not in step_ids:
                self._add(
                    errors,
                    "FLOW_STEP_NEXT_NOT_FOUND",
                    "FLOW_STEP_NEXT_NOT_FOUND: next references unknown step_id "
                    f"(step={step.step_id}, next={next_step_id})",
                )

        if step.step_type == StepType.SWITCH.value:
            raw_cases = step.body.get("cases", {})
            if isinstance(raw_cases, dict):
                for target in raw_cases.values():
                    target_step_id = str(target).strip()
                    if target_step_id and target_step_id not in step_ids:
                        self._add(
                            errors,
                            "FLOW_SWITCH_CASE_TARGET_NOT_FOUND",
                            "FLOW_SWITCH_CASE_TARGET_NOT_FOUND: switch case "
                            "references unknown step_id "
                            f"(step={step.step_id}, target={target_step_id})",
                        )
            raw_default = str(step.body.get("default", "")).strip()
            if raw_default and raw_default not in step_ids:
                self._add(
                    errors,
                    "FLOW_SWITCH_DEFAULT_TARGET_NOT_FOUND",
                    "FLOW_SWITCH_DEFAULT_TARGET_NOT_FOUND: switch default "
                    "references unknown step_id "
                    f"(step={step.step_id}, target={raw_default})",
                )

        if step.step_type == StepType.WHEN.value:
            raw_branches = step.body.get("branches", [])
            if isinstance(raw_branches, list):
                for branch in raw_branches:
                    if not isinstance(branch, dict):
                        continue
                    target_step_id = str(branch.get("then", "")).strip()
                    if target_step_id and target_step_id not in step_ids:
                        self._add(
                            errors,
                            "FLOW_WHEN_BRANCH_TARGET_NOT_FOUND",
                            "FLOW_WHEN_BRANCH_TARGET_NOT_FOUND: when branch "
                            "references unknown step_id "
                            f"(step={step.step_id}, target={target_step_id})",
                        )
            raw_default = str(step.body.get("default", "")).strip()
            if raw_default and raw_default not in step_ids:
                self._add(
                    errors,
                    "FLOW_WHEN_DEFAULT_TARGET_NOT_FOUND",
                    "FLOW_WHEN_DEFAULT_TARGET_NOT_FOUND: when default references unknown step_id "
                    f"(step={step.step_id}, target={raw_default})",
                )

    def _check_required_fields(self, step: _ParsedStep, errors: list[FlowCheckError]) -> None:
        required_fields = {
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
            StepType.MCP.value: ("server", "FLOW_MCP_SERVER_MISSING", "mcp step requires server"),
        }
        if step.step_type in required_fields:
            field, code, text = required_fields[step.step_type]
            if not str(step.body.get(field, "")).strip():
                self._add(errors, code, f"{code}: {text} (step={step.step_id})")

        if step.step_type == StepType.NOTIFY.value:
            raw_format = step.body.get("format")
            if raw_format is not None:
                format_value = str(raw_format).strip()
                supported_formats = {item.value for item in NotifyOutputFormat}
                if format_value not in supported_formats:
                    self._add(
                        errors,
                        "FLOW_NOTIFY_FORMAT_UNSUPPORTED",
                        "FLOW_NOTIFY_FORMAT_UNSUPPORTED: notify step format must be "
                        "simple, structured or markdown "
                        f"(step={step.step_id}, format={format_value})",
                    )
            self._check_notify_action(step, errors)

        if step.step_type == StepType.AGENT.value and not str(step.body.get("task", "")).strip():
            self._add(
                errors,
                "FLOW_AGENT_TASK_MISSING",
                f"FLOW_AGENT_TASK_MISSING: agent step requires task (step={step.step_id})",
            )

        if (
            step.step_type == StepType.SEND.value
            and not str(step.body.get("key", "")).strip()
        ):
            self._add(
                errors,
                "FLOW_SEND_KEY_MISSING",
                f"FLOW_SEND_KEY_MISSING: send step requires key (step={step.step_id})",
            )

        if (
            step.step_type == StepType.SEND.value
            and not str(step.body.get("message", "")).strip()
        ):
            self._add(
                errors,
                "FLOW_SEND_MESSAGE_MISSING",
                f"FLOW_SEND_MESSAGE_MISSING: send step requires message (step={step.step_id})",
            )

        if step.step_type == StepType.SEND.value:
            channel = str(step.body.get("channel", "")).strip().lower()
            if channel and channel != "whatsapp":
                self._add(
                    errors,
                    "FLOW_SEND_CHANNEL_UNSUPPORTED",
                    "FLOW_SEND_CHANNEL_UNSUPPORTED: send step supports only whatsapp "
                    f"(step={step.step_id}, channel={channel})",
                )

        if (
            step.step_type == StepType.WAIT_WEBHOOK.value
            and not str(step.body.get("key", "")).strip()
        ):
            self._add(
                errors,
                "FLOW_WAIT_WEBHOOK_KEY_MISSING",
                "FLOW_WAIT_WEBHOOK_KEY_MISSING: wait_webhook step requires key "
                f"(step={step.step_id})",
            )

        if (
            step.step_type == StepType.WAIT_CHANNEL.value
            and not str(step.body.get("key", "")).strip()
        ):
            self._add(
                errors,
                "FLOW_WAIT_CHANNEL_KEY_MISSING",
                "FLOW_WAIT_CHANNEL_KEY_MISSING: wait_channel step requires key "
                f"(step={step.step_id})",
            )

        if step.step_type == StepType.MCP.value and not str(step.body.get("tool", "")).strip():
            self._add(
                errors,
                "FLOW_MCP_TOOL_MISSING",
                f"FLOW_MCP_TOOL_MISSING: mcp step requires tool (step={step.step_id})",
            )

    def _check_templates(
        self,
        step: _ParsedStep,
        step_ids: set[str],
        parsed_steps: list[_ParsedStep],
        errors: list[FlowCheckError],
    ) -> None:
        step_index_by_id = {item.step_id: item.index for item in parsed_steps}

        for field, value in self._walk_values(step.body):
            if not isinstance(value, str):
                continue
            for expression in _TEMPLATE_RE.findall(value):
                self._check_expression(
                    step_id=step.step_id,
                    step_index=step.index,
                    field=field,
                    expression=expression.strip(),
                    step_ids=step_ids,
                    step_index_by_id=step_index_by_id,
                    errors=errors,
                )

    def _check_expression(
        self,
        *,
        step_id: str,
        step_index: int,
        field: str,
        expression: str,
        step_ids: set[str],
        step_index_by_id: dict[str, int],
        errors: list[FlowCheckError],
    ) -> None:
        if expression.startswith("step_executions.") and ".output.value" in expression:
            self._add(
                errors,
                "FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS",
                "FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS: direct output.value "
                "access is not allowed "
                f"(step={step_id}, field={field})",
            )
            return

        if expression.startswith("output_value("):
            output_match = _OUTPUT_VALUE_CALL_RE.match(expression)
            if output_match is None:
                self._add(
                    errors,
                    "FLOW_OUTPUT_VALUE_INVALID_SYNTAX",
                    "FLOW_OUTPUT_VALUE_INVALID_SYNTAX: invalid output_value expression "
                    f"(step={step_id}, field={field})",
                )
                return

            raw_args = output_match.group(1).strip()
            args = [part.strip() for part in raw_args.split(",")] if raw_args else []
            if len(args) != 1:
                self._add(
                    errors,
                    "FLOW_OUTPUT_VALUE_INVALID_ARITY",
                    "FLOW_OUTPUT_VALUE_INVALID_ARITY: output_value expects exactly one argument "
                    f"(step={step_id}, field={field})",
                )
                return

            literal_match = _STRING_LITERAL_RE.match(args[0])
            if literal_match is None:
                self._add(
                    errors,
                    "FLOW_OUTPUT_VALUE_STEP_ID_NOT_LITERAL",
                    "FLOW_OUTPUT_VALUE_STEP_ID_NOT_LITERAL: output_value "
                    "step_id must be a string literal "
                    f"(step={step_id}, field={field})",
                )
                return

            ref_step_id = literal_match.group(2).strip()
            if ref_step_id not in step_ids:
                self._add(
                    errors,
                    "FLOW_OUTPUT_VALUE_STEP_NOT_FOUND",
                    "FLOW_OUTPUT_VALUE_STEP_NOT_FOUND: referenced step_id does not exist "
                    f"(step={step_id}, ref={ref_step_id})",
                )
                return

            if step_index_by_id[ref_step_id] >= step_index:
                self._add(
                    errors,
                    "FLOW_OUTPUT_VALUE_FORWARD_REFERENCE",
                    "FLOW_OUTPUT_VALUE_FORWARD_REFERENCE: output_value must "
                    "reference a previous step "
                    f"(step={step_id}, ref={ref_step_id})",
                )
                return

            return

        if _UNSUPPORTED_HELPER_RE.match(expression):
            self._add(
                errors,
                "FLOW_OUTPUT_VALUE_UNSUPPORTED_HELPER",
                "FLOW_OUTPUT_VALUE_UNSUPPORTED_HELPER: unsupported template helper "
                f"(step={step_id}, field={field})",
            )

    def _walk_values(self, value: Any, path: str = "") -> list[tuple[str, Any]]:
        if isinstance(value, dict):
            items: list[tuple[str, Any]] = []
            for key, item in value.items():
                next_path = f"{path}.{key}" if path else str(key)
                items.extend(self._walk_values(item, next_path))
            return items

        if isinstance(value, list):
            items: list[tuple[str, Any]] = []
            for index, item in enumerate(value):
                next_path = f"{path}[{index}]"
                items.extend(self._walk_values(item, next_path))
            return items

        return [(path or "<value>", value)]

    def _invalid(
        self,
        errors: list[FlowCheckError],
        code: str,
        message: str,
    ) -> FlowCheckResult:
        self._add(errors, code, message)
        return FlowCheckResult(status=FlowCheckStatus.INVALID, errors=errors)

    def _result(self, errors: list[FlowCheckError]) -> FlowCheckResult:
        if errors:
            return FlowCheckResult(status=FlowCheckStatus.INVALID, errors=errors)
        return FlowCheckResult(status=FlowCheckStatus.VALID, errors=[])

    def _add(self, errors: list[FlowCheckError], code: str, message: str) -> None:
        errors.append(FlowCheckError(code=code, message=message))

    def _check_notify_action(
        self,
        step: _ParsedStep,
        errors: list[FlowCheckError],
    ) -> None:
        raw_action = step.body.get("action")
        if raw_action is None:
            return

        if not isinstance(raw_action, dict):
            self._add(
                errors,
                "FLOW_NOTIFY_ACTION_INVALID",
                f"FLOW_NOTIFY_ACTION_INVALID: notify action must be an object "
                f"(step={step.step_id})",
            )
            return

        raw_type = str(raw_action.get("type", "")).strip()
        if raw_type != ActionType.OPEN_URL.value:
            self._add(
                errors,
                "FLOW_NOTIFY_ACTION_TYPE_UNSUPPORTED",
                "FLOW_NOTIFY_ACTION_TYPE_UNSUPPORTED: notify action type must be "
                f"{ActionType.OPEN_URL.value} (step={step.step_id})",
            )

        if not str(raw_action.get("label", "")).strip():
            self._add(
                errors,
                "FLOW_NOTIFY_ACTION_LABEL_MISSING",
                "FLOW_NOTIFY_ACTION_LABEL_MISSING: notify action requires non-empty "
                f"label (step={step.step_id})",
            )

        raw_message = raw_action.get("message")
        if raw_message is not None and not isinstance(raw_message, str):
            self._add(
                errors,
                "FLOW_NOTIFY_ACTION_MESSAGE_INVALID",
                "FLOW_NOTIFY_ACTION_MESSAGE_INVALID: notify action message must be "
                f"a string (step={step.step_id})",
            )

        raw_url = str(raw_action.get("url", "")).strip()
        if not raw_url:
            self._add(
                errors,
                "FLOW_NOTIFY_ACTION_URL_MISSING",
                "FLOW_NOTIFY_ACTION_URL_MISSING: notify action requires non-empty "
                f"url (step={step.step_id})",
            )
            return

        if (
            not raw_url.startswith(("http://", "https://"))
            and _FULL_TEMPLATE_RE.match(raw_url) is None
        ):
            self._add(
                errors,
                "FLOW_NOTIFY_ACTION_URL_UNSUPPORTED",
                "FLOW_NOTIFY_ACTION_URL_UNSUPPORTED: notify action url must use "
                f"http(s) (step={step.step_id})",
            )

        raw_auto = raw_action.get("auto")
        if raw_auto is not None and not isinstance(raw_auto, bool):
            self._add(
                errors,
                "FLOW_NOTIFY_ACTION_AUTO_INVALID",
                "FLOW_NOTIFY_ACTION_AUTO_INVALID: notify action auto "
                f"must be boolean (step={step.step_id})",
            )
