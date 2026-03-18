from types import SimpleNamespace

import pytest

from skiller.application.use_cases.handle_input import HandleInputUseCase

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: object | None) -> None:
        self.run = run
        self.events: list[dict[str, object]] = []
        self.created_input_events: list[dict[str, object]] = []

    def get_run(self, run_id: str):  # noqa: ANN201
        _ = run_id
        return self.run

    def create_input_event(self, run_id: str, step_id: str, payload: dict[str, object]) -> str:
        self.created_input_events.append(
            {"run_id": run_id, "step_id": step_id, "payload": payload}
        )
        return "input-1"

    def append_event(
        self, event_type: str, payload: dict[str, object], run_id: str | None = None
    ) -> str:
        self.events.append({"type": event_type, "payload": payload, "run_id": run_id})
        return "event-1"


def test_handle_input_rejects_missing_text() -> None:
    use_case = HandleInputUseCase(store=_FakeStore(run=None))

    result = use_case.execute("run-1", text="")

    assert result.accepted is False
    assert result.error == "text is required"


def test_handle_input_rejects_when_current_step_is_not_wait_input() -> None:
    run = SimpleNamespace(
        status="WAITING",
        current="start",
        skill_snapshot={"steps": [{"id": "start", "type": "notify"}]},
    )
    use_case = HandleInputUseCase(store=_FakeStore(run=run))

    result = use_case.execute("run-1", text="hello")

    assert result.accepted is False
    assert result.error == "Run 'run-1' current step 'start' is not wait_input"


def test_handle_input_persists_event_for_wait_input_step() -> None:
    run = SimpleNamespace(
        status="WAITING",
        current="ask_user",
        skill_snapshot={"steps": [{"id": "ask_user", "type": "wait_input"}]},
    )
    store = _FakeStore(run=run)
    use_case = HandleInputUseCase(store=store)

    result = use_case.execute("run-1", text="database timeout")

    assert result.accepted is True
    assert result.run_ids == ["run-1"]
    assert result.event_id == "input-1"
    assert store.created_input_events == [
        {
            "run_id": "run-1",
            "step_id": "ask_user",
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
