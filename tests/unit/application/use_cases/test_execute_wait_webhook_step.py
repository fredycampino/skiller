import pytest

from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.step_execution_result import StepExecutionStatus
from skiller.domain.external_event_type import ExternalEventType
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import WaitWebhookOutput
from skiller.domain.wait_type import WaitType

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(
        self,
        *,
        active_wait: dict[str, object] | None = None,
        webhook_event: dict[str, object] | None = None,
    ) -> None:
        self.active_wait = active_wait
        self.webhook_event = webhook_event
        self.updated: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.created_waits: list[dict[str, object]] = []
        self.resolved_wait_ids: list[str] = []

    def get_active_wait(
        self,
        run_id: str,
        step_id: str,
        *,
        wait_type: WaitType,
    ) -> dict[str, object] | None:
        _ = (run_id, step_id, wait_type)
        return self.active_wait

    def get_latest_external_event(
        self,
        *,
        event_type: ExternalEventType,
        run_id: str | None = None,
        step_id: str | None = None,
        webhook: str | None = None,
        key: str | None = None,
        since_created_at: str | None = None,
    ) -> dict[str, object] | None:
        _ = (event_type, run_id, step_id, webhook, key, since_created_at)
        return self.webhook_event

    def resolve_wait(self, wait_id: str) -> None:
        self.resolved_wait_ids.append(wait_id)

    def create_wait(
        self,
        run_id: str,
        *,
        step_id: str,
        wait_type: WaitType,
        webhook: str | None = None,
        key: str | None = None,
        expires_at: str | None = None,
    ) -> str:
        self.created_waits.append(
            {
                "run_id": run_id,
                "wait_type": wait_type,
                "webhook": webhook,
                "key": key,
                "step_id": step_id,
                "expires_at": expires_at,
            }
        )
        return "wait-1"

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )

    def append_event(
        self, event_type: str, payload: dict[str, object], run_id: str | None = None
    ) -> str:
        self.events.append({"type": event_type, "payload": payload, "run_id": run_id})
        return "event-1"


def _build_current_step(*, next_step_id: object = "done") -> CurrentStep:
    step: dict[str, object] = {
        "webhook": "test",
        "key": "42",
    }
    if next_step_id is not None:
        step["next"] = next_step_id

    return CurrentStep(
        run_id="run-1",
        step_index=0,
        step_id="wait_test",
        step_type=StepType.WAIT_WEBHOOK,
        step=step,
        context=RunContext(inputs={}, step_executions={}),
    )


def test_wait_webhook_returns_waiting_and_persists_wait() -> None:
    store = _FakeStore()
    use_case = ExecuteWaitWebhookStepUseCase(store=store)
    current_step = _build_current_step()

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.WAITING
    assert result.next_step_id is None
    assert result.execution is not None
    assert result.execution.output == WaitWebhookOutput(
        text="Waiting webhook: test:42.",
        webhook="test",
        key="42",
    )
    assert store.created_waits == [
        {
            "run_id": "run-1",
            "wait_type": WaitType.WEBHOOK,
            "webhook": "test",
            "key": "42",
            "step_id": "wait_test",
            "expires_at": None,
        }
    ]
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.WAITING,
            "current": "wait_test",
            "context": current_step.context,
        }
    ]
    assert store.events == []


def test_wait_webhook_returns_next_when_event_exists_and_next_declared() -> None:
    store = _FakeStore(
        active_wait={"id": "wait-1", "created_at": "2026-03-11 10:00:00"},
        webhook_event={"id": "webhook-1", "payload": {"ok": True}},
    )
    use_case = ExecuteWaitWebhookStepUseCase(store=store)
    current_step = _build_current_step()

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == WaitWebhookOutput(
        text="Webhook received: test:42.",
        webhook="test",
        key="42",
        payload={"ok": True},
    )
    assert current_step.context.step_executions["wait_test"] == result.execution
    assert store.resolved_wait_ids == ["wait-1"]
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "done",
            "context": current_step.context,
        }
    ]
    assert store.events == []


def test_wait_webhook_returns_completed_when_event_exists_and_next_missing() -> None:
    store = _FakeStore(webhook_event={"id": "webhook-1", "payload": {"ok": True}})
    use_case = ExecuteWaitWebhookStepUseCase(store=store)
    current_step = _build_current_step(next_step_id=None)

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert result.execution is not None
    assert result.execution.output == WaitWebhookOutput(
        text="Webhook received: test:42.",
        webhook="test",
        key="42",
        payload={"ok": True},
    )
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": None,
            "context": current_step.context,
        }
    ]


def test_wait_webhook_rejects_empty_next_when_declared() -> None:
    store = _FakeStore(webhook_event={"id": "webhook-1", "payload": {"ok": True}})
    use_case = ExecuteWaitWebhookStepUseCase(store=store)
    current_step = _build_current_step(next_step_id="   ")

    with pytest.raises(ValueError, match="requires non-empty next"):
        use_case.execute(current_step)
