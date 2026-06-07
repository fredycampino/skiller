from skiller.application.use_cases.flow.flow_check_model import FlowCheckError
from skiller.domain.action.action_model import ActionType, EndActionTrigger
from skiller.domain.flow.flow_raw_definition import FlowRawDefinition


class FlowEndActionChecker:
    def check(
        self,
        *,
        flow: FlowRawDefinition,
        errors: list[FlowCheckError],
    ) -> None:
        raw_flow = flow.raw
        if not isinstance(raw_flow, dict):
            return

        for trigger in EndActionTrigger:
            self._check_trigger(
                trigger=trigger,
                raw_config=raw_flow.get(trigger.value),
                errors=errors,
            )

    def _check_trigger(
        self,
        *,
        trigger: EndActionTrigger,
        raw_config: object,
        errors: list[FlowCheckError],
    ) -> None:
        if raw_config is None:
            return

        if not isinstance(raw_config, dict):
            errors.append(
                FlowCheckError(
                    code="FLOW_END_ACTION_INVALID",
                    message="FLOW_END_ACTION_INVALID: end action config must be an "
                    f"object (trigger={trigger.value})",
                )
            )
            return

        raw_cleanup = raw_config.get("cleanup")
        cleanup_enabled = raw_cleanup is True
        if raw_cleanup is not None and not isinstance(raw_cleanup, bool):
            errors.append(
                FlowCheckError(
                    code="FLOW_END_ACTION_CLEANUP_INVALID",
                    message="FLOW_END_ACTION_CLEANUP_INVALID: end action cleanup must "
                    f"be boolean (trigger={trigger.value})",
                )
            )
            return

        raw_action = raw_config.get("action")
        if raw_action is None and cleanup_enabled:
            return

        if not isinstance(raw_action, dict):
            errors.append(
                FlowCheckError(
                    code="FLOW_END_ACTION_ACTION_INVALID",
                    message="FLOW_END_ACTION_ACTION_INVALID: end action requires action "
                    f"object or cleanup true (trigger={trigger.value})",
                )
            )
            return

        self._check_action(trigger=trigger, raw_action=raw_action, errors=errors)

    def _check_action(
        self,
        *,
        trigger: EndActionTrigger,
        raw_action: dict[object, object],
        errors: list[FlowCheckError],
    ) -> None:
        raw_type = str(raw_action.get("type", "")).strip()
        if raw_type != ActionType.RUN.value:
            errors.append(
                FlowCheckError(
                    code="FLOW_END_ACTION_TYPE_UNSUPPORTED",
                    message="FLOW_END_ACTION_TYPE_UNSUPPORTED: end action type must "
                    f"be {ActionType.RUN.value} (trigger={trigger.value})",
                )
            )

        if not str(raw_action.get("label", "")).strip():
            errors.append(
                FlowCheckError(
                    code="FLOW_END_ACTION_LABEL_MISSING",
                    message="FLOW_END_ACTION_LABEL_MISSING: end action requires "
                    f"non-empty label (trigger={trigger.value})",
                )
            )

        if not str(raw_action.get("arg", "")).strip():
            errors.append(
                FlowCheckError(
                    code="FLOW_END_ACTION_ARG_MISSING",
                    message="FLOW_END_ACTION_ARG_MISSING: end action requires "
                    f"non-empty arg (trigger={trigger.value})",
                )
            )

        raw_params = raw_action.get("params")
        if raw_params is not None and not isinstance(raw_params, str):
            errors.append(
                FlowCheckError(
                    code="FLOW_END_ACTION_PARAMS_INVALID",
                    message="FLOW_END_ACTION_PARAMS_INVALID: end action params must "
                    f"be string (trigger={trigger.value})",
                )
            )

        raw_auto = raw_action.get("auto")
        if raw_auto is not None and not isinstance(raw_auto, bool):
            errors.append(
                FlowCheckError(
                    code="FLOW_END_ACTION_AUTO_INVALID",
                    message="FLOW_END_ACTION_AUTO_INVALID: end action auto must be "
                    f"boolean (trigger={trigger.value})",
                )
            )
