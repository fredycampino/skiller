import pytest

from skiller.application.use_cases.run.mark_notify_action_done import (
    MarkNotifyActionDoneInput,
    MarkNotifyActionDoneStatus,
    MarkNotifyActionDoneUseCase,
)
from skiller.domain.action.action_model import ActionStatus, ActionType, OpenUrlAction, RunAction
from skiller.domain.event.event_model import (
    ActionDonePayload,
    RuntimeEventDraft,
    RuntimeEventType,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunStatus
from skiller.domain.step.step_execution_model import (
    NotifyOutput,
    StepExecution,
)
from skiller.domain.step.step_type import StepType

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: Run | None = None) -> None:
        self.run = run
        self.updated_runs: list[dict[str, object]] = []

    def get_run(self, run_id: str) -> Run | None:
        if self.run is None or self.run.id != run_id:
            return None
        return self.run

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated_runs.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )


class _FakeEvents:
    def __init__(self, events: list[RuntimeEventDraft] | None = None) -> None:
        self.events = events or []

    def append_event(self, event: RuntimeEventDraft) -> str:
        self.events.append(event)
        return "event-1"

    def list_events(self, run_id: str, *, after_sequence=None, limit=None):  # noqa: ANN001
        return [event for event in self.events if event.run_id == run_id]


def test_mark_notify_action_done_emits_action_done_event() -> None:
    run = _build_run()
    store = _FakeStore(run)
    events = _FakeEvents()
    use_case = MarkNotifyActionDoneUseCase(store=store, events=events)

    result = use_case.execute(_request("auth-link-action"))

    assert result.status == MarkNotifyActionDoneStatus.DONE
    assert result.changed is True
    execution = run.context.step_executions["auth_link"]
    assert isinstance(execution.output, NotifyOutput)
    assert execution.output.action == OpenUrlAction(
        uid="auth-link-action",
        label="Open authorization",
        url="https://example.com/oauth/start",
    )
    assert store.updated_runs == []
    assert len(events.events) == 1
    event = events.events[0]
    assert event.run_id == "run-1"
    assert event.type == RuntimeEventType.ACTION_DONE
    assert event.step_id == "auth_link"
    assert event.step_type == "notify"
    assert event.payload.uid == "auth-link-action"
    assert event.payload.type == ActionType.OPEN_URL
    assert event.payload.status == ActionStatus.DONE


def test_mark_notify_action_done_is_idempotent() -> None:
    run = _build_run()
    store = _FakeStore(run)
    events = _FakeEvents(
        [
            RuntimeEventDraft(
                run_id="run-1",
                type=RuntimeEventType.ACTION_DONE,
                step_id="auth_link",
                step_type="notify",
                payload=ActionDonePayload(
                    uid="auth-link-action",
                    type=ActionType.OPEN_URL,
                    status=ActionStatus.DONE,
                ),
            )
        ]
    )
    use_case = MarkNotifyActionDoneUseCase(store=store, events=events)

    result = use_case.execute(_request("auth-link-action"))

    assert result.status == MarkNotifyActionDoneStatus.DONE
    assert result.changed is False
    assert result.step_id == "auth_link"
    assert store.updated_runs == []
    assert len(events.events) == 1


def test_mark_notify_action_done_returns_action_not_found() -> None:
    run = _build_run()
    store = _FakeStore(run)
    events = _FakeEvents()
    use_case = MarkNotifyActionDoneUseCase(store=store, events=events)

    result = use_case.execute(_request("missing"))

    assert result.status == MarkNotifyActionDoneStatus.ACTION_NOT_FOUND
    assert result.changed is False
    assert result.step_id is None
    assert result.error == "Action 'missing' not found in run 'run-1'"
    assert store.updated_runs == []
    assert events.events == []


def test_mark_notify_action_done_returns_action_not_found_for_regular_notify() -> None:
    context = RunContext(
        inputs={},
        step_executions={
            "show": StepExecution(
                step_type=StepType.NOTIFY,
                output=NotifyOutput(text="ok", message="ok"),
            )
        },
    )
    run = _build_run_with_context(context)
    store = _FakeStore(run)
    events = _FakeEvents()
    use_case = MarkNotifyActionDoneUseCase(store=store, events=events)

    result = use_case.execute(_request("show"))

    assert result.status == MarkNotifyActionDoneStatus.ACTION_NOT_FOUND
    assert result.changed is False
    assert result.step_id is None
    assert result.error == "Action 'show' not found in run 'run-1'"
    assert store.updated_runs == []
    assert events.events == []


def test_mark_notify_action_done_emits_run_action_done_event() -> None:
    context = RunContext(
        inputs={},
        step_executions={
            "run_followup": StepExecution(
                step_type=StepType.NOTIFY,
                output=NotifyOutput(
                    text="Run follow-up",
                    message="Run follow-up",
                    action=RunAction(
                        uid="run-followup-action",
                        label="Run follow-up",
                        arg="support_agent",
                    ),
                ),
            )
        },
    )
    run = _build_run_with_context(context)
    store = _FakeStore(run)
    events = _FakeEvents()
    use_case = MarkNotifyActionDoneUseCase(store=store, events=events)

    result = use_case.execute(_request("run-followup-action"))

    assert result.status == MarkNotifyActionDoneStatus.DONE
    assert result.changed is True
    assert result.step_id == "run_followup"
    event = events.events[0]
    assert event.step_id == "run_followup"
    assert event.payload == ActionDonePayload(
        uid="run-followup-action",
        type=ActionType.RUN,
        status=ActionStatus.DONE,
    )


def _build_run() -> Run:
    context = RunContext(
        inputs={},
        step_executions={
            "auth_link": StepExecution(
                step_type=StepType.NOTIFY,
                output=NotifyOutput(
                    text="Authorize the app",
                    message="Authorize the app",
                    action=OpenUrlAction(
                        uid="auth-link-action",
                        label="Open authorization",
                        url="https://example.com/oauth/start",
                    ),
                ),
            )
        },
    )
    return _build_run_with_context(context)


def _request(action_uid: str) -> MarkNotifyActionDoneInput:
    return MarkNotifyActionDoneInput(run_id="run-1", action_uid=action_uid)


def _build_run_with_context(context: RunContext) -> Run:
    return Run(
        id="run-1",
        source="internal",
        ref="notify_action",
        snapshot={},
        status=RunStatus.SUCCEEDED.value,
        current=None,
        context=context,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
