from dataclasses import dataclass
from enum import StrEnum

from skiller.domain.action.action_model import Action, ActionStatus
from skiller.domain.event.event_model import (
    ActionDonePayload,
    RuntimeEventDraft,
    RuntimeEventType,
)
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.step_execution_model import (
    NotifyOutput,
    StepExecution,
)
from skiller.domain.step.step_type import StepType


class MarkNotifyActionDoneStatus(StrEnum):
    DONE = "DONE"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    ACTION_NOT_FOUND = "ACTION_NOT_FOUND"


@dataclass(frozen=True)
class MarkNotifyActionDoneResult:
    run_id: str
    action_uid: str
    status: MarkNotifyActionDoneStatus
    changed: bool
    step_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class MarkNotifyActionDoneInput:
    run_id: str
    action_uid: str


class MarkNotifyActionDoneUseCase:
    def __init__(
        self,
        store: RunStorePort,
        events: RuntimeEventStorePort,
    ) -> None:
        self.store = store
        self.events = events

    def execute(self, request: MarkNotifyActionDoneInput) -> MarkNotifyActionDoneResult:
        run = self.store.get_run(request.run_id)
        if run is None:
            return MarkNotifyActionDoneResult(
                run_id=request.run_id,
                action_uid=request.action_uid,
                status=MarkNotifyActionDoneStatus.RUN_NOT_FOUND,
                changed=False,
                error=f"Run '{request.run_id}' not found",
            )

        action_ref = _find_notify_action(
            step_executions=run.context.step_executions,
            action_uid=request.action_uid,
        )
        if action_ref is None:
            return MarkNotifyActionDoneResult(
                run_id=request.run_id,
                action_uid=request.action_uid,
                status=MarkNotifyActionDoneStatus.ACTION_NOT_FOUND,
                changed=False,
                error=f"Action '{request.action_uid}' not found in run '{request.run_id}'",
            )
        step_id, action = action_ref

        for event in self.events.list_events(request.run_id):
            payload = event.payload
            if (
                event.type == RuntimeEventType.ACTION_DONE
                and isinstance(payload, ActionDonePayload)
                and payload.uid == request.action_uid
                and payload.status == ActionStatus.DONE
            ):
                return MarkNotifyActionDoneResult(
                    run_id=request.run_id,
                    action_uid=request.action_uid,
                    status=MarkNotifyActionDoneStatus.DONE,
                    changed=False,
                    step_id=step_id,
                )

        self.events.append_event(
            RuntimeEventDraft(
                run_id=request.run_id,
                type=RuntimeEventType.ACTION_DONE,
                step_id=step_id,
                step_type=StepType.NOTIFY.value,
                payload=ActionDonePayload(
                    uid=action.uid,
                    type=action.type,
                    status=ActionStatus.DONE,
                ),
            )
        )
        return MarkNotifyActionDoneResult(
            run_id=request.run_id,
            action_uid=request.action_uid,
            status=MarkNotifyActionDoneStatus.DONE,
            changed=True,
            step_id=step_id,
        )


def _find_notify_action(
    *,
    step_executions: dict[str, StepExecution],
    action_uid: str,
) -> tuple[str, Action] | None:
    for step_id, execution in step_executions.items():
        output = execution.output
        if execution.step_type != StepType.NOTIFY or not isinstance(output, NotifyOutput):
            continue
        action = output.action
        if action is None or action.uid != action_uid:
            continue
        return step_id, action
    return None
