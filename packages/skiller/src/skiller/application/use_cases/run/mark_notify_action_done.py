from dataclasses import dataclass, replace
from enum import StrEnum

from skiller.domain.event.event_model import (
    ActionDonePayload,
    RuntimeEventDraft,
    RuntimeEventType,
)
from skiller.domain.event.runtime_event_store_port import RuntimeEventStorePort
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.step.step_execution_model import (
    NotifyActionStatus,
    NotifyActionType,
    NotifyOpenUrlAction,
    NotifyOutput,
)
from skiller.domain.step.step_type import StepType


class MarkNotifyActionDoneStatus(StrEnum):
    DONE = "DONE"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    STEP_NOT_FOUND = "STEP_NOT_FOUND"
    NOT_ACTION = "NOT_ACTION"


@dataclass(frozen=True)
class MarkNotifyActionDoneResult:
    run_id: str
    step_id: str
    status: MarkNotifyActionDoneStatus
    changed: bool
    error: str | None = None


@dataclass(frozen=True)
class MarkNotifyActionDoneInput:
    run_id: str
    step_id: str


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
                step_id=request.step_id,
                status=MarkNotifyActionDoneStatus.RUN_NOT_FOUND,
                changed=False,
                error=f"Run '{request.run_id}' not found",
            )

        execution = run.context.step_executions.get(request.step_id)
        if execution is None:
            return MarkNotifyActionDoneResult(
                run_id=request.run_id,
                step_id=request.step_id,
                status=MarkNotifyActionDoneStatus.STEP_NOT_FOUND,
                changed=False,
                error=f"Step '{request.step_id}' not found in run '{request.run_id}'",
            )

        output = execution.output
        if (
            execution.step_type != StepType.NOTIFY
            or not isinstance(output, NotifyOutput)
            or output.action_type != NotifyActionType.OPEN_URL
            or not isinstance(output.action, NotifyOpenUrlAction)
        ):
            return MarkNotifyActionDoneResult(
                run_id=request.run_id,
                step_id=request.step_id,
                status=MarkNotifyActionDoneStatus.NOT_ACTION,
                changed=False,
                error=f"Step '{request.step_id}' is not a notify action",
            )

        if output.action.status == NotifyActionStatus.DONE:
            return MarkNotifyActionDoneResult(
                run_id=request.run_id,
                step_id=request.step_id,
                status=MarkNotifyActionDoneStatus.DONE,
                changed=False,
            )

        action = replace(output.action, status=NotifyActionStatus.DONE)
        run.context.step_executions[request.step_id] = replace(
            execution,
            output=replace(output, action=action),
        )
        self.store.update_run(request.run_id, context=run.context)
        self.events.append_event(
            RuntimeEventDraft(
                run_id=request.run_id,
                type=RuntimeEventType.ACTION_DONE,
                step_id=request.step_id,
                step_type=StepType.NOTIFY.value,
                payload=ActionDonePayload(
                    action_type=output.action_type.value,
                    status=NotifyActionStatus.DONE.value,
                ),
            )
        )
        return MarkNotifyActionDoneResult(
            run_id=request.run_id,
            step_id=request.step_id,
            status=MarkNotifyActionDoneStatus.DONE,
            changed=True,
        )
