from types import SimpleNamespace

import pytest

from skiller.application.use_cases.handle_input import HandleInputUseCase
from skiller.domain.match_type import MatchType
from skiller.domain.source_type import SourceType

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: object | None) -> None:
        self.run = run
        self.events: list[dict[str, object]] = []
        self.created_external_events: list[dict[str, object]] = []

    def get_run(self, run_id: str):  # noqa: ANN201
        _ = run_id
        return self.run

    def create_external_event(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        payload: dict[str, object],
        run_id: str | None = None,
        step_id: str | None = None,
        external_id: str | None = None,
        dedup_key: str | None = None,
    ) -> str:
        self.created_external_events.append(
            {
                "source_type": source_type,
                "source_name": source_name,
                "match_type": match_type,
                "match_key": match_key,
                "run_id": run_id,
                "step_id": step_id,
                "external_id": external_id,
                "dedup_key": dedup_key,
                "payload": payload,
            }
        )
        return "input-1"

    def append_event(
        self, event_type: str, payload: dict[str, object], run_id: str | None = None
    ) -> str:
        self.events.append({"type": event_type, "payload": payload, "run_id": run_id})
        return "event-1"


def test_handle_input_rejects_missing_text() -> None:
    store = _FakeStore(run=None)
    use_case = HandleInputUseCase(
        run_store=store,
        external_event_store=store,
        runtime_event_store=store,
    )

    result = use_case.execute("run-1", text="")

    assert result.accepted is False
    assert result.error == "text is required"


def test_handle_input_rejects_when_current_step_is_not_wait_input() -> None:
    run = SimpleNamespace(
        status="WAITING",
        current="show_message",
        skill_snapshot={"steps": [{"notify": "show_message"}]},
    )
    store = _FakeStore(run=run)
    use_case = HandleInputUseCase(
        run_store=store,
        external_event_store=store,
        runtime_event_store=store,
    )

    result = use_case.execute("run-1", text="hello")

    assert result.accepted is False
    assert result.error == "Run 'run-1' current step 'show_message' is not wait_input"


def test_handle_input_persists_event_for_wait_input_step() -> None:
    run = SimpleNamespace(
        status="WAITING",
        current="ask_user",
        skill_snapshot={"steps": [{"wait_input": "ask_user"}]},
    )
    store = _FakeStore(run=run)
    use_case = HandleInputUseCase(
        run_store=store,
        external_event_store=store,
        runtime_event_store=store,
    )

    result = use_case.execute("run-1", text="database timeout")

    assert result.accepted is True
    assert result.run_ids == ["run-1"]
    assert result.event_id == "input-1"
    assert store.created_external_events == [
        {
            "source_type": SourceType.INPUT,
            "source_name": "manual",
            "match_type": MatchType.RUN,
            "match_key": "run-1",
            "run_id": "run-1",
            "step_id": "ask_user",
            "external_id": None,
            "dedup_key": None,
            "payload": {"text": "database timeout"},
        }
    ]
    assert store.events == [
        {
            "type": "INPUT_RECEIVED",
            "payload": {"step": "ask_user", "payload": {"text": "database timeout"}},
            "run_id": "run-1",
        }
    ]
