import pytest

from skiller.application.use_cases.execute.execute_wait_input_step import (
    ExecuteWaitInputStepUseCase,
)
from skiller.application.use_cases.render.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.shared.step_execution_result import StepExecutionStatus
from skiller.domain.match_type import MatchType
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.source_type import SourceType
from skiller.domain.step_execution_model import StepExecution, WaitInputOutput
from skiller.domain.wait_type import WaitType

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(
        self,
        *,
        active_wait: dict[str, object] | None = None,
        input_event: dict[str, object] | None = None,
    ) -> None:
        self.active_wait = active_wait
        self.input_event = input_event
        self.updated: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.created_waits: list[dict[str, object]] = []
        self.resolved_wait_ids: list[str] = []
        self.consumed_event_ids: list[dict[str, str]] = []
        self.latest_event_query: dict[str, object] | None = None

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
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        run_id: str | None = None,
        step_id: str | None = None,
        since_created_at: str | None = None,
    ) -> dict[str, object] | None:
        self.latest_event_query = {
            "source_type": source_type,
            "source_name": source_name,
            "match_type": match_type,
            "match_key": match_key,
            "run_id": run_id,
            "step_id": step_id,
            "since_created_at": since_created_at,
        }
        return self.input_event

    def resolve_wait(self, wait_id: str) -> None:
        self.resolved_wait_ids.append(wait_id)

    def consume_external_event(self, event_id: str, *, run_id: str) -> bool:
        self.consumed_event_ids.append({"event_id": event_id, "run_id": run_id})
        return True

    def create_wait(
        self,
        run_id: str,
        *,
        step_id: str,
        wait_type: WaitType,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        expires_at: str | None = None,
    ) -> str:
        self.created_waits.append(
            {
                "run_id": run_id,
                "step_id": step_id,
                "wait_type": wait_type,
                "source_type": source_type,
                "source_name": source_name,
                "match_type": match_type,
                "match_key": match_key,
                "expires_at": expires_at,
            }
        )
        return "input-wait-1"

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
        "prompt": "Write a short summary",
    }
    if next_step_id is not None:
        step["next"] = next_step_id

    return CurrentStep(
        run_id="run-1",
        step_index=0,
        step_id="ask_user",
        step_type=StepType.WAIT_INPUT,
        step=step,
        context=RunContext(inputs={}, step_executions={}),
        run_created_at="2026-03-18 09:00:00",
    )


def test_wait_input_returns_waiting_and_persists_wait() -> None:
    store = _FakeStore()
    use_case = ExecuteWaitInputStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )

    result = use_case.execute(_build_current_step())

    assert result.status == StepExecutionStatus.WAITING
    assert result.execution is not None
    assert result.execution.output == WaitInputOutput(
        text="Write a short summary",
        prompt="Write a short summary",
    )
    assert store.created_waits == [
        {
            "run_id": "run-1",
            "step_id": "ask_user",
            "wait_type": WaitType.INPUT,
            "source_type": SourceType.INPUT,
            "source_name": "manual",
            "match_type": MatchType.RUN,
            "match_key": "run-1",
            "expires_at": None,
        }
    ]
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.WAITING,
            "current": "ask_user",
            "context": _build_current_step().context,
        }
    ]
    assert store.events == []
    assert store.latest_event_query is not None
    assert store.latest_event_query["since_created_at"] == "2026-03-18 09:00:00"


def test_wait_input_returns_next_when_event_exists_and_next_declared() -> None:
    store = _FakeStore(
        active_wait={"id": "input-wait-1", "created_at": "2026-03-18 10:00:00"},
        input_event={"id": "input-1", "payload": {"text": "database timeout"}},
    )
    use_case = ExecuteWaitInputStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )
    current_step = _build_current_step()

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == WaitInputOutput(
        text="Input received.",
        prompt="Write a short summary",
        payload={"text": "database timeout"},
    )
    assert current_step.context.step_executions["ask_user"] == result.execution
    assert result.execution.evaluation == {"input_event_id": "input-1"}
    assert store.consumed_event_ids == [{"event_id": "input-1", "run_id": "run-1"}]
    assert store.resolved_wait_ids == ["input-wait-1"]
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": "done",
            "context": current_step.context,
        }
    ]
    assert store.events == []
    assert store.latest_event_query is not None
    assert store.latest_event_query["since_created_at"] == "2026-03-18 09:00:00"


def test_wait_input_returns_completed_when_event_exists_and_next_missing() -> None:
    store = _FakeStore(input_event={"id": "input-1", "payload": {"text": "database timeout"}})
    use_case = ExecuteWaitInputStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )
    current_step = _build_current_step(next_step_id=None)

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.execution is not None
    assert result.execution.output == WaitInputOutput(
        text="Input received.",
        prompt="Write a short summary",
        payload={"text": "database timeout"},
    )
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.RUNNING,
            "current": None,
            "context": current_step.context,
        }
    ]
    assert store.consumed_event_ids == [{"event_id": "input-1", "run_id": "run-1"}]
    assert store.latest_event_query is not None
    assert store.latest_event_query["since_created_at"] == "2026-03-18 09:00:00"


def test_wait_input_ignores_input_event_already_consumed_for_same_step() -> None:
    store = _FakeStore(
        input_event={"id": "input-1", "payload": {"text": "database timeout"}},
    )
    use_case = ExecuteWaitInputStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )
    current_step = _build_current_step()
    current_step.context.step_executions["ask_user"] = StepExecution(
        step_type=StepType.WAIT_INPUT,
        input={"prompt": "Write a short summary"},
        evaluation={"input_event_id": "input-1"},
        output=WaitInputOutput(
            text="Input received.",
            prompt="Write a short summary",
            payload={"text": "database timeout"},
        ),
    )

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.WAITING
    assert result.execution is not None
    assert result.execution.output == WaitInputOutput(
        text="Write a short summary",
        prompt="Write a short summary",
    )
    assert store.created_waits == [
        {
            "run_id": "run-1",
            "step_id": "ask_user",
            "wait_type": WaitType.INPUT,
            "source_type": SourceType.INPUT,
            "source_name": "manual",
            "match_type": MatchType.RUN,
            "match_key": "run-1",
            "expires_at": None,
        }
    ]
    assert store.resolved_wait_ids == []
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.WAITING,
            "current": "ask_user",
            "context": current_step.context,
        }
    ]
    assert store.events == []


def test_wait_input_rejects_empty_next_when_declared() -> None:
    store = _FakeStore(input_event={"id": "input-1", "payload": {"text": "database timeout"}})
    use_case = ExecuteWaitInputStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )

    with pytest.raises(ValueError, match="requires non-empty next"):
        use_case.execute(_build_current_step(next_step_id="   "))
