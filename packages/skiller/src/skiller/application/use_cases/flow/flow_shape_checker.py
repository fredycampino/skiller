from skiller.application.use_cases.flow.flow_check_model import (
    FlowCheckError,
    FlowShapeCheck,
)
from skiller.domain.flow.flow_raw_definition import FlowRawDefinition


class FlowShapeChecker:
    def check(
        self,
        *,
        flow: FlowRawDefinition,
        errors: list[FlowCheckError],
    ) -> FlowShapeCheck:
        if not isinstance(flow.raw, dict):
            errors.append(
                FlowCheckError(
                    code="FLOW_FORMAT_INVALID",
                    message="FLOW_FORMAT_INVALID: flow must be an object",
                )
            )
            return FlowShapeCheck(start="", steps=None, can_continue=False)

        name = _raw_text(flow.name)
        if not name:
            errors.append(
                FlowCheckError(
                    code="FLOW_NAME_MISSING",
                    message="FLOW_NAME_MISSING: flow requires non-empty name",
                )
            )

        start = _raw_text(flow.start)
        if not start:
            errors.append(
                FlowCheckError(
                    code="FLOW_START_MISSING",
                    message="FLOW_START_MISSING: flow requires non-empty start",
                )
            )

        if "steps" not in flow.raw:
            errors.append(
                FlowCheckError(
                    code="FLOW_STEPS_MISSING",
                    message="FLOW_STEPS_MISSING: flow requires steps",
                )
            )
            return FlowShapeCheck(start=start, steps=None, can_continue=False)

        if flow.steps is None:
            errors.append(
                FlowCheckError(
                    code="FLOW_STEPS_INVALID",
                    message="FLOW_STEPS_INVALID: flow steps must be a list",
                )
            )
            return FlowShapeCheck(start=start, steps=None, can_continue=False)

        if not flow.steps:
            errors.append(
                FlowCheckError(
                    code="FLOW_STEPS_EMPTY",
                    message="FLOW_STEPS_EMPTY: flow requires at least one step",
                )
            )
            return FlowShapeCheck(start=start, steps=None, can_continue=False)

        return FlowShapeCheck(start=start, steps=flow.steps, can_continue=True)


def _raw_text(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()
