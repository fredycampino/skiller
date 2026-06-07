import re

from skiller.application.use_cases.flow.flow_check_model import (
    FlowCheckError,
    ParsedFlowStep,
)
from skiller.domain.action.action_model import ActionType

_FULL_TEMPLATE_RE = re.compile(r"^\s*{{\s*([^}]+?)\s*}}\s*$")


class FlowNotifyActionChecker:
    def check(
        self,
        *,
        step: ParsedFlowStep,
        errors: list[FlowCheckError],
    ) -> None:
        raw_action = step.body.get("action")
        if raw_action is None:
            return

        if not isinstance(raw_action, dict):
            errors.append(
                FlowCheckError(
                    code="FLOW_NOTIFY_ACTION_INVALID",
                    message="FLOW_NOTIFY_ACTION_INVALID: notify action must be an "
                    f"object (step={step.step_id})",
                )
            )
            return

        action_type = self._action_type(step=step, raw_action=raw_action, errors=errors)
        if action_type is None:
            return

        self._check_label(step=step, raw_action=raw_action, errors=errors)
        self._check_auto(step=step, raw_action=raw_action, errors=errors)
        if action_type == ActionType.OPEN_URL:
            self._check_message(step=step, raw_action=raw_action, errors=errors)
            self._check_url(step=step, raw_action=raw_action, errors=errors)
            return

        self._check_arg(step=step, raw_action=raw_action, errors=errors)
        self._check_params(step=step, raw_action=raw_action, errors=errors)

    def _action_type(
        self,
        *,
        step: ParsedFlowStep,
        raw_action: dict[object, object],
        errors: list[FlowCheckError],
    ) -> ActionType | None:
        raw_type = str(raw_action.get("type", "")).strip()
        supported_types = {ActionType.OPEN_URL.value, ActionType.RUN.value}
        if raw_type in supported_types:
            return ActionType(raw_type)

        errors.append(
            FlowCheckError(
                code="FLOW_NOTIFY_ACTION_TYPE_UNSUPPORTED",
                message="FLOW_NOTIFY_ACTION_TYPE_UNSUPPORTED: notify action type "
                f"must be {ActionType.OPEN_URL.value} or {ActionType.RUN.value} "
                f"(step={step.step_id})",
            )
        )
        return None

    def _check_label(
        self,
        *,
        step: ParsedFlowStep,
        raw_action: dict[object, object],
        errors: list[FlowCheckError],
    ) -> None:
        if str(raw_action.get("label", "")).strip():
            return

        errors.append(
            FlowCheckError(
                code="FLOW_NOTIFY_ACTION_LABEL_MISSING",
                message="FLOW_NOTIFY_ACTION_LABEL_MISSING: notify action requires "
                f"non-empty label (step={step.step_id})",
            )
        )

    def _check_message(
        self,
        *,
        step: ParsedFlowStep,
        raw_action: dict[object, object],
        errors: list[FlowCheckError],
    ) -> None:
        raw_message = raw_action.get("message")
        if raw_message is None or isinstance(raw_message, str):
            return

        errors.append(
            FlowCheckError(
                code="FLOW_NOTIFY_ACTION_MESSAGE_INVALID",
                message="FLOW_NOTIFY_ACTION_MESSAGE_INVALID: notify action message "
                f"must be a string (step={step.step_id})",
            )
        )

    def _check_url(
        self,
        *,
        step: ParsedFlowStep,
        raw_action: dict[object, object],
        errors: list[FlowCheckError],
    ) -> None:
        raw_url = str(raw_action.get("url", "")).strip()
        if not raw_url:
            errors.append(
                FlowCheckError(
                    code="FLOW_NOTIFY_ACTION_URL_MISSING",
                    message="FLOW_NOTIFY_ACTION_URL_MISSING: notify action requires "
                    f"non-empty url (step={step.step_id})",
                )
            )
            return

        if raw_url.startswith(("http://", "https://")):
            return

        if _FULL_TEMPLATE_RE.match(raw_url) is not None:
            return

        errors.append(
            FlowCheckError(
                code="FLOW_NOTIFY_ACTION_URL_UNSUPPORTED",
                message="FLOW_NOTIFY_ACTION_URL_UNSUPPORTED: notify action url "
                f"must use http(s) (step={step.step_id})",
            )
        )

    def _check_auto(
        self,
        *,
        step: ParsedFlowStep,
        raw_action: dict[object, object],
        errors: list[FlowCheckError],
    ) -> None:
        raw_auto = raw_action.get("auto")
        if raw_auto is None or isinstance(raw_auto, bool):
            return

        errors.append(
            FlowCheckError(
                code="FLOW_NOTIFY_ACTION_AUTO_INVALID",
                message="FLOW_NOTIFY_ACTION_AUTO_INVALID: notify action auto must "
                f"be boolean (step={step.step_id})",
            )
        )

    def _check_arg(
        self,
        *,
        step: ParsedFlowStep,
        raw_action: dict[object, object],
        errors: list[FlowCheckError],
    ) -> None:
        if str(raw_action.get("arg", "")).strip():
            return

        errors.append(
            FlowCheckError(
                code="FLOW_NOTIFY_ACTION_ARG_MISSING",
                message="FLOW_NOTIFY_ACTION_ARG_MISSING: notify run action requires "
                f"non-empty arg (step={step.step_id})",
            )
        )

    def _check_params(
        self,
        *,
        step: ParsedFlowStep,
        raw_action: dict[object, object],
        errors: list[FlowCheckError],
    ) -> None:
        raw_params = raw_action.get("params")
        if raw_params is None or isinstance(raw_params, str):
            return

        errors.append(
            FlowCheckError(
                code="FLOW_NOTIFY_ACTION_PARAMS_INVALID",
                message="FLOW_NOTIFY_ACTION_PARAMS_INVALID: notify run action params "
                f"must be string (step={step.step_id})",
            )
        )
