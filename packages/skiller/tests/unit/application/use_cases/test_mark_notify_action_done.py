import pytest

from skiller.application.use_cases.run.mark_notify_action_done import (
    MarkNotifyActionDoneInput,
    MarkNotifyActionDoneStatus,
    MarkNotifyActionDoneUseCase,
)
from skiller.domain.event.event_model import RuntimeEventDraft, RuntimeEventType
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunStatus
from skiller.domain.step.step_execution_model import (
    NotifyActionStatus,
    NotifyActionType,
    NotifyOpenUrlAction,
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
    def __init__(self) -> None:
        self.events: list[RuntimeEventDraft] = []

    def append_event(self, event: RuntimeEventDraft) -> str:
        self.events.append(event)
        return "event-1"


def test_mark_notify_action_done_updates_action_status() -> None:
    run = _build_run(action_status=NotifyActionStatus.PENDING)
    store = _FakeStore(run)
    events = _FakeEvents()
    use_case = MarkNotifyActionDoneUseCase(store=store, events=events)

    result = use_case.execute(_request("auth_link"))

    assert result.status == MarkNotifyActionDoneStatus.DONE
    assert result.changed is True
    execution = run.context.step_executions["auth_link"]
    assert isinstance(execution.output, NotifyOutput)
    assert execution.output.action == NotifyOpenUrlAction(
        label="Open authorization",
        url="https://example.com/oauth/start",
        status=NotifyActionStatus.DONE,
    )
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": None,
            "current": None,
            "context": run.context,
        }
    ]
    assert len(events.events) == 1
    event = events.events[0]
    assert event.run_id == "run-1"
    assert event.type == RuntimeEventType.ACTION_DONE
    assert event.step_id == "auth_link"
    assert event.step_type == "notify"
    assert event.payload.action_type == "open_url"
    assert event.payload.status == "done"


def test_mark_notify_action_done_is_idempotent() -> None:
    run = _build_run(action_status=NotifyActionStatus.DONE)
    store = _FakeStore(run)
    events = _FakeEvents()
    use_case = MarkNotifyActionDoneUseCase(store=store, events=events)

    result = use_case.execute(_request("auth_link"))

    assert result.status == MarkNotifyActionDoneStatus.DONE
    assert result.changed is False
    assert store.updated_runs == []
    assert events.events == []


def test_mark_notify_action_done_returns_step_not_found() -> None:
    run = _build_run(action_status=NotifyActionStatus.PENDING)
    store = _FakeStore(run)
    events = _FakeEvents()
    use_case = MarkNotifyActionDoneUseCase(store=store, events=events)

    result = use_case.execute(_request("missing"))

    assert result.status == MarkNotifyActionDoneStatus.STEP_NOT_FOUND
    assert result.changed is False
    assert result.error == "Step 'missing' not found in run 'run-1'"
    assert store.updated_runs == []
    assert events.events == []


def test_mark_notify_action_done_returns_not_action_for_regular_notify() -> None:
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

    assert result.status == MarkNotifyActionDoneStatus.NOT_ACTION
    assert result.changed is False
    assert result.error == "Step 'show' is not a notify action"
    assert store.updated_runs == []
    assert events.events == []


def _build_run(action_status: NotifyActionStatus) -> Run:
    context = RunContext(
        inputs={},
        step_executions={
            "auth_link": StepExecution(
                step_type=StepType.NOTIFY,
                output=NotifyOutput(
                    text="Authorize the app",
                    message="Authorize the app",
                    action_type=NotifyActionType.OPEN_URL,
                    action=NotifyOpenUrlAction(
                        label="Open authorization",
                        url="https://example.com/oauth/start",
                        status=action_status,
                    ),
                ),
            )
        },
    )
    return _build_run_with_context(context)


def _request(step_id: str) -> MarkNotifyActionDoneInput:
    return MarkNotifyActionDoneInput(run_id="run-1", step_id=step_id)


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
