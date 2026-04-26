import pytest

from skiller.application.use_cases.execute.execute_wait_channel_step import (
    ExecuteWaitChannelStepUseCase,
)
from skiller.application.use_cases.render.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.shared.step_execution_result import StepExecutionStatus
from skiller.domain.match_type import MatchType
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.source_type import SourceType
from skiller.domain.step_execution_model import WaitChannelOutput
from skiller.domain.wait_type import WaitType

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(
        self,
        *,
        active_wait: dict[str, object] | None = None,
        channel_event: dict[str, object] | None = None,
    ) -> None:
        self.active_wait = active_wait
        self.channel_event = channel_event
        self.updated: list[dict[str, object]] = []
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
        return self.channel_event

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
        return "channel-wait-1"

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )


def _build_current_step(*, next_step_id: object = "done") -> CurrentStep:
    step: dict[str, object] = {
        "channel": "whatsapp",
        "key": "all",
    }
    if next_step_id is not None:
        step["next"] = next_step_id

    return CurrentStep(
        run_id="run-1",
        step_index=0,
        step_id="listen_whatsapp",
        step_type=StepType.WAIT_CHANNEL,
        step=step,
        context=RunContext(inputs={}, step_executions={}),
        run_created_at="2026-04-07 09:00:00",
    )


def test_wait_channel_returns_waiting_and_persists_wait() -> None:
    store = _FakeStore()
    use_case = ExecuteWaitChannelStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )
    current_step = _build_current_step()

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.WAITING
    assert result.execution is not None
    assert result.execution.output == WaitChannelOutput(
        text="Waiting channel: whatsapp:all.",
        channel="whatsapp",
        key="all",
    )
    assert store.created_waits == [
        {
            "run_id": "run-1",
            "step_id": "listen_whatsapp",
            "wait_type": WaitType.CHANNEL,
            "source_type": SourceType.CHANNEL,
            "source_name": "whatsapp",
            "match_type": MatchType.CHANNEL_KEY,
            "match_key": "all",
            "expires_at": None,
        }
    ]
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.WAITING,
            "current": "listen_whatsapp",
            "context": current_step.context,
        }
    ]
    assert store.latest_event_query is None


def test_wait_channel_returns_next_when_event_exists() -> None:
    store = _FakeStore(
        active_wait={"id": "channel-wait-1", "created_at": "2026-04-07 10:00:00"},
        channel_event={
            "id": "channel-1",
            "payload": {
                "key": "172584771580071@lid",
                "text": "hola",
            },
        },
    )
    use_case = ExecuteWaitChannelStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )
    current_step = _build_current_step()

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == WaitChannelOutput(
        text="Channel message received: whatsapp:172584771580071@lid.",
        channel="whatsapp",
        key="172584771580071@lid",
        payload={"key": "172584771580071@lid", "text": "hola"},
    )
    assert store.consumed_event_ids == [{"event_id": "channel-1", "run_id": "run-1"}]
    assert store.resolved_wait_ids == ["channel-wait-1"]
    assert store.latest_event_query is not None
    assert store.latest_event_query["since_created_at"] == "2026-04-07 10:00:00"


def test_wait_channel_ignores_stale_message_timestamp() -> None:
    store = _FakeStore(
        active_wait={"id": "channel-wait-1", "created_at": "2026-04-20 17:58:17"},
        channel_event={
            "id": "channel-1",
            "payload": {
                "key": "172584771580071@lid",
                "text": "hola",
                "timestamp": 1775388655,
            },
        },
    )
    use_case = ExecuteWaitChannelStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )
    current_step = _build_current_step()

    result = use_case.execute(current_step)

    assert result.status == StepExecutionStatus.WAITING
    assert store.consumed_event_ids == [{"event_id": "channel-1", "run_id": "run-1"}]
    assert store.resolved_wait_ids == []
    assert store.updated == [
        {
            "run_id": "run-1",
            "status": RunStatus.WAITING,
            "current": "listen_whatsapp",
            "context": current_step.context,
        }
    ]
