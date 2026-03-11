import pytest

from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import Run, RunStatus

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run
        self.updates: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self.run

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        current: str | None = None,
        context: RunContext | None = None,
    ) -> None:
        self.updates.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )

    def append_event(self, event_type: str, payload: dict[str, object], run_id: str | None = None) -> str:
        self.events.append({"type": event_type, "payload": payload, "run_id": run_id})
        return "event-1"


def test_fail_run_marks_failed_and_logs_error() -> None:
    run = Run(
        id="run-1",
        skill_source="internal",
        skill_ref="demo",
        skill_snapshot={"steps": [{"id": "done", "type": "notify"}]},
        status=RunStatus.RUNNING.value,
        current="done",
        context=RunContext(inputs={}, results={}),
        created_at="2026-03-07 10:00:00",
        updated_at="2026-03-07 10:00:00",
    )
    store = _FakeStore(run)
    use_case = FailRunUseCase(store)

    use_case.execute("run-1", error="boom")

    assert store.updates == [
        {
            "run_id": "run-1",
            "status": RunStatus.FAILED,
            "current": "done",
            "context": run.context,
        }
    ]
    assert store.events == [
        {
            "type": "RUN_FAILED",
            "payload": {"error": "boom"},
            "run_id": "run-1",
        }
    ]
