import pytest

from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import Run, RunStatus

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run
        self.updates: list[dict[str, object]] = []

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

def test_fail_run_marks_failed() -> None:
    run = Run(
        id="run-1",
        skill_source="internal",
        skill_ref="demo",
        skill_snapshot={"start": "done", "steps": [{"notify": "done"}]},
        status=RunStatus.RUNNING.value,
        current="done",
        context=RunContext(inputs={}, step_executions={}),
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
