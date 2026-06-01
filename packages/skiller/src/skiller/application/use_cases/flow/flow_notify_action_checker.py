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

        self._check_type(step=step, raw_action=raw_action, errors=errors)
        self._check_label(step=step, raw_action=raw_action, errors=errors)
        self._check_message(step=step, raw_action=raw_action, errors=errors)
        self._check_url(step=step, raw_action=raw_action, errors=errors)
        self._check_auto(step=step, raw_action=raw_action, errors=errors)

    def _check_type(
        self,
        *,
        step: ParsedFlowStep,
        raw_action: dict[object, object],
        errors: list[FlowCheckError],
    ) -> None:
        raw_type = str(raw_action.get("type", "")).strip()
        if raw_type == ActionType.OPEN_URL.value:
            return

        errors.append(
            FlowCheckError(
                code="FLOW_NOTIFY_ACTION_TYPE_UNSUPPORTED",
                message="FLOW_NOTIFY_ACTION_TYPE_UNSUPPORTED: notify action type "
                f"must be {ActionType.OPEN_URL.value} (step={step.step_id})",
            )
        )

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
