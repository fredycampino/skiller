import re
from typing import Any

from skiller.application.use_cases.flow.flow_check_model import (
    FlowCheckError,
    ParsedFlowStep,
)
from skiller.domain.action.action_model import EndActionTrigger
from skiller.domain.flow.flow_raw_definition import FlowRawDefinition

_TEMPLATE_RE = re.compile(r"{{\s*([^}]+?)\s*}}")
_OUTPUT_VALUE_CALL_RE = re.compile(r'^output_value\((.*)\)((?:\.[A-Za-z_][A-Za-z0-9_]*)*)$')
_STRING_LITERAL_RE = re.compile(r'^(["\'])([^"\']+)\1$')
_UNSUPPORTED_HELPER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*\(")


class FlowTemplateChecker:
    def check_steps(
        self,
        *,
        steps: list[ParsedFlowStep],
        step_ids: set[str],
        errors: list[FlowCheckError],
    ) -> None:
        step_index_by_id = {item.step_id: item.index for item in steps}

        for step in steps:
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

    def check_end_actions(
        self,
        *,
        flow: FlowRawDefinition,
        step_ids: set[str],
        steps: list[ParsedFlowStep],
        errors: list[FlowCheckError],
    ) -> None:
        raw_flow = flow.raw
        if not isinstance(raw_flow, dict):
            return

        step_index_by_id = {item.step_id: item.index for item in steps}
        end_index = max((step.index for step in steps), default=-1) + 1

        for trigger in EndActionTrigger:
            raw_config = raw_flow.get(trigger.value)
            if not isinstance(raw_config, dict):
                continue

            raw_action = raw_config.get("action")
            if not isinstance(raw_action, dict):
                continue

            for field, value in self._walk_values(raw_action, f"{trigger.value}.action"):
                if not isinstance(value, str):
                    continue
                for expression in _TEMPLATE_RE.findall(value):
                    self._check_expression(
                        step_id=trigger.value,
                        step_index=end_index,
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
            errors.append(
                FlowCheckError(
                    code="FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS",
                    message="FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS: direct "
                    f"output.value access is not allowed (step={step_id}, field={field})",
                )
            )
            return

        if expression.startswith("output_value("):
            self._check_output_value_expression(
                step_id=step_id,
                step_index=step_index,
                field=field,
                expression=expression,
                step_ids=step_ids,
                step_index_by_id=step_index_by_id,
                errors=errors,
            )
            return

        if _UNSUPPORTED_HELPER_RE.match(expression):
            errors.append(
                FlowCheckError(
                    code="FLOW_OUTPUT_VALUE_UNSUPPORTED_HELPER",
                    message="FLOW_OUTPUT_VALUE_UNSUPPORTED_HELPER: unsupported "
                    f"template helper (step={step_id}, field={field})",
                )
            )

    def _check_output_value_expression(
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
        output_match = _OUTPUT_VALUE_CALL_RE.match(expression)
        if output_match is None:
            errors.append(
                FlowCheckError(
                    code="FLOW_OUTPUT_VALUE_INVALID_SYNTAX",
                    message="FLOW_OUTPUT_VALUE_INVALID_SYNTAX: invalid output_value "
                    f"expression (step={step_id}, field={field})",
                )
            )
            return

        raw_args = output_match.group(1).strip()
        args = [part.strip() for part in raw_args.split(",")] if raw_args else []
        if len(args) != 1:
            errors.append(
                FlowCheckError(
                    code="FLOW_OUTPUT_VALUE_INVALID_ARITY",
                    message="FLOW_OUTPUT_VALUE_INVALID_ARITY: output_value expects "
                    f"exactly one argument (step={step_id}, field={field})",
                )
            )
            return

        literal_match = _STRING_LITERAL_RE.match(args[0])
        if literal_match is None:
            errors.append(
                FlowCheckError(
                    code="FLOW_OUTPUT_VALUE_STEP_ID_NOT_LITERAL",
                    message="FLOW_OUTPUT_VALUE_STEP_ID_NOT_LITERAL: output_value "
                    f"step_id must be a string literal (step={step_id}, field={field})",
                )
            )
            return

        ref_step_id = literal_match.group(2).strip()
        if ref_step_id not in step_ids:
            errors.append(
                FlowCheckError(
                    code="FLOW_OUTPUT_VALUE_STEP_NOT_FOUND",
                    message="FLOW_OUTPUT_VALUE_STEP_NOT_FOUND: referenced step_id "
                    f"does not exist (step={step_id}, ref={ref_step_id})",
                )
            )
            return

        if step_index_by_id[ref_step_id] >= step_index:
            errors.append(
                FlowCheckError(
                    code="FLOW_OUTPUT_VALUE_FORWARD_REFERENCE",
                    message="FLOW_OUTPUT_VALUE_FORWARD_REFERENCE: output_value must "
                    f"reference a previous step (step={step_id}, ref={ref_step_id})",
                )
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
