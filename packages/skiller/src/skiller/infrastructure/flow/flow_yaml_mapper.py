from typing import Any

from skiller.domain.action.action_model import EndActionTrigger
from skiller.domain.flow.flow_raw_definition import (
    FlowRawDefinition,
    FlowRawStepDefinition,
    RawAction,
    RawEndActionDefinition,
)


class FlowYamlMapper:
    def to_flow(self, raw: object) -> FlowRawDefinition:
        if not isinstance(raw, dict):
            return FlowRawDefinition(
                name=None,
                start=None,
                steps=None,
                raw=raw,
            )

        raw_steps = raw.get("steps")
        steps = self._to_steps(raw_steps) if isinstance(raw_steps, list) else None

        return FlowRawDefinition(
            name=_raw_string(raw.get("name")),
            start=_raw_string(raw.get("start")),
            steps=steps,
            on_success=self._to_end_action(
                trigger=EndActionTrigger.ON_SUCCESS.value,
                value=raw.get(EndActionTrigger.ON_SUCCESS.value),
            ),
            on_error=self._to_end_action(
                trigger=EndActionTrigger.ON_ERROR.value,
                value=raw.get(EndActionTrigger.ON_ERROR.value),
            ),
            raw=raw,
        )

    def _to_steps(self, raw_steps: list[Any]) -> tuple[FlowRawStepDefinition, ...]:
        steps: list[FlowRawStepDefinition] = []
        for index, raw_step in enumerate(raw_steps):
            steps.append(self._to_step(index=index, raw_step=raw_step))
        return tuple(steps)

    def _to_step(self, *, index: int, raw_step: object) -> FlowRawStepDefinition:
        if not isinstance(raw_step, dict):
            return FlowRawStepDefinition(
                index=index,
                step_id=None,
                step_type=None,
                body=None,
                raw=raw_step,
            )

        if not raw_step:
            return FlowRawStepDefinition(
                index=index,
                step_id=None,
                step_type=None,
                body={},
                raw=raw_step,
            )

        step_type = next(iter(raw_step))
        return FlowRawStepDefinition(
            index=index,
            step_id=_raw_string(raw_step.get(step_type)),
            step_type=step_type,
            body={key: value for key, value in raw_step.items() if key != step_type},
            raw=raw_step,
        )

    def _to_end_action(self, *, trigger: str, value: object) -> RawEndActionDefinition | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            return RawEndActionDefinition(
                trigger=trigger,
                action=None,
            )

        raw_action = value.get("action")
        if not isinstance(raw_action, dict):
            return RawEndActionDefinition(
                trigger=trigger,
                action=None,
            )

        return RawEndActionDefinition(
            trigger=trigger,
            action=RawAction(
                type=_raw_string(raw_action.get("type")),
                label=_raw_string(raw_action.get("label")),
                message=_raw_string(raw_action.get("message")),
                url=_raw_string(raw_action.get("url")),
                arg=_raw_string(raw_action.get("arg")),
                params=_raw_string(raw_action.get("params")),
                auto=raw_action.get("auto"),
                raw=raw_action,
            ),
        )


def _raw_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None
