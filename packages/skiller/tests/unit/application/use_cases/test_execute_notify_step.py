import pytest

from skiller.application.action.action_mapper import ActionMapper
from skiller.application.action.action_uid_factory import ActionUidFactory
from skiller.application.use_cases.execute.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.domain.action.action_model import OpenUrlAction, RunAction
from skiller.domain.event.event_model import RuntimeEventDraft
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.current_step_model import CurrentStep
from skiller.domain.step.step_execution_model import (
    NotifyOutput,
    NotifyOutputFormat,
)
from skiller.domain.step.step_execution_result_model import StepExecutionStatus
from skiller.domain.step.step_type import StepType

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self) -> None:
        self.updated_runs: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated_runs.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )

    def append_event(self, event: RuntimeEventDraft) -> str:
        self.events.append(
            {"type": event.type.value, "payload": event.payload, "run_id": event.run_id}
        )
        return "event-1"


class _FakeActionUidFactory(ActionUidFactory):
    def __init__(self, *uids: str) -> None:
        self.uids = list(uids)

    def new_uid(self) -> str:
        if not self.uids:
            return "action-uid"
        return self.uids.pop(0)


def _build_next_step(step: dict[str, object]) -> CurrentStep:
    return CurrentStep(
        run_id="run-1",
        step_index=0,
        step_id="show_message",
        step_type=StepType.NOTIFY,
        step=step,
        context=RunContext(inputs={}, step_executions={}),
    )


def _use_case(store: _FakeStore) -> ExecuteNotifyStepUseCase:
    action_mapper = ActionMapper(_FakeActionUidFactory("action-uid"))
    return ExecuteNotifyStepUseCase(store=store, action_mapper=action_mapper)


def test_notify_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step({"message": "ok", "next": "done"})

    result = use_case.execute(next_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == NotifyOutput(text="ok", message="ok")
    assert result.execution.to_public_output_dict() == {
        "text": "ok",
        "value": {
            "message": "ok",
            "format": NotifyOutputFormat.SIMPLE,
        },
        "body_ref": None,
    }
    assert next_step.context.step_executions["show_message"] == result.execution
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "done",
            "context": next_step.context,
        }
    ]
    assert store.events == []


def test_notify_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step({"message": "ok"})

    result = use_case.execute(next_step)

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert result.execution is not None
    assert result.execution.output == NotifyOutput(text="ok", message="ok")
    assert store.updated_runs == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": None,
            "context": next_step.context,
        }
    ]


def test_notify_persists_declared_output_format() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step({"message": "**ok**", "format": "markdown"})

    result = use_case.execute(next_step)

    assert result.execution is not None
    assert result.execution.output == NotifyOutput(
        text="**ok**",
        message="**ok**",
        format=NotifyOutputFormat.MARKDOWN,
    )
    assert result.execution.to_public_output_dict() == {
        "text": "**ok**",
        "value": {
            "message": "**ok**",
            "format": NotifyOutputFormat.MARKDOWN,
        },
        "body_ref": None,
    }


def test_notify_persists_action_message() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step(
        {
            "message": "Authorize the app",
            "action": {
                "type": "open_url",
                "label": "Open authorization",
                "message": "Continue in the browser.",
                "url": "https://example.com/oauth/start",
                "auto": True,
            },
        }
    )

    result = use_case.execute(next_step)

    assert result.execution is not None
    assert result.execution.output == NotifyOutput(
        text="Authorize the app",
        message="Authorize the app",
        format=NotifyOutputFormat.SIMPLE,
        action=OpenUrlAction(
            uid="action-uid",
            label="Open authorization",
            message="Continue in the browser.",
            url="https://example.com/oauth/start",
            auto=True,
        ),
    )
    assert result.execution.to_public_output_dict() == {
        "text": "Authorize the app",
        "value": {
            "message": "Authorize the app",
            "format": NotifyOutputFormat.SIMPLE,
            "action": {
                "type": "open_url",
                "uid": "action-uid",
                "label": "Open authorization",
                "message": "Continue in the browser.",
                "url": "https://example.com/oauth/start",
                "auto": True,
            },
        },
        "body_ref": None,
    }


def test_notify_defaults_action_message_to_notify_message() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step(
        {
            "message": "Authorize the app",
            "action": {
                "type": "open_url",
                "label": "Open authorization",
                "url": "https://example.com/oauth/start",
                "auto": True,
            },
        }
    )

    result = use_case.execute(next_step)

    assert result.execution is not None
    assert result.execution.output == NotifyOutput(
        text="Authorize the app",
        message="Authorize the app",
        format=NotifyOutputFormat.SIMPLE,
        action=OpenUrlAction(
            uid="action-uid",
            label="Open authorization",
            message="Authorize the app",
            url="https://example.com/oauth/start",
            auto=True,
        ),
    )
    assert result.execution.to_public_output_dict()["value"]["action"] == {
        "type": "open_url",
        "uid": "action-uid",
        "label": "Open authorization",
        "message": "Authorize the app",
        "url": "https://example.com/oauth/start",
        "auto": True,
    }


def test_notify_persists_run_action() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step(
        {
            "message": "Run follow-up",
            "action": {
                "type": "run",
                "label": "Run support",
                "arg": "support_agent",
                "params": "--source stui",
                "auto": True,
            },
        }
    )

    result = use_case.execute(next_step)

    assert result.execution is not None
    assert result.execution.output == NotifyOutput(
        text="Run follow-up",
        message="Run follow-up",
        format=NotifyOutputFormat.SIMPLE,
        action=RunAction(
            uid="action-uid",
            label="Run support",
            arg="support_agent",
            params="--source stui",
            auto=True,
        ),
    )
    assert result.execution.to_public_output_dict()["value"]["action"] == {
        "type": "run",
        "uid": "action-uid",
        "label": "Run support",
        "arg": "support_agent",
        "auto": True,
        "params": "--source stui",
    }


def test_notify_rejects_empty_next_when_declared() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step({"message": "ok", "next": "   "})

    with pytest.raises(ValueError, match="requires non-empty next"):
        use_case.execute(next_step)


def test_notify_rejects_unknown_output_format() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step({"message": "ok", "format": "html"})

    with pytest.raises(ValueError, match="unsupported format 'html'"):
        use_case.execute(next_step)

    assert next_step.context.step_executions == {}
    assert store.updated_runs == []


def test_notify_rejects_invalid_action_auto() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step(
        {
            "message": "Authorize the app",
            "action": {
                "type": "open_url",
                "label": "Open authorization",
                "url": "https://example.com/oauth/start",
                "auto": "false",
            },
        }
    )

    with pytest.raises(ValueError, match="action auto must be boolean"):
        use_case.execute(next_step)

    assert next_step.context.step_executions == {}
    assert store.updated_runs == []


def test_notify_rejects_invalid_action_message() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step(
        {
            "message": "Authorize the app",
            "action": {
                "type": "open_url",
                "label": "Open authorization",
                "message": ["invalid"],
                "url": "https://example.com/oauth/start",
            },
        }
    )

    with pytest.raises(ValueError, match="action message must be string"):
        use_case.execute(next_step)

    assert next_step.context.step_executions == {}
    assert store.updated_runs == []


def test_notify_rejects_invalid_message_before_persisting_step_execution() -> None:
    store = _FakeStore()
    use_case = _use_case(store)
    next_step = _build_next_step({"message": None})

    with pytest.raises(ValueError, match="requires string message"):
        use_case.execute(next_step)

    assert next_step.context.step_executions == {}
    assert store.updated_runs == []
