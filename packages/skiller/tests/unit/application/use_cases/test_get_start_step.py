import pytest

from skiller.application.use_cases.run.get_start_step import GetStartStepUseCase
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunStatus

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: Run | None) -> None:
        self.run = run
        self.updates: list[dict[str, object]] = []

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self.run

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updates.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )


def _build_run(snapshot: object) -> Run:
    return Run(
        id="run-1",
        source="internal",
        ref="demo",
        snapshot=snapshot,  # type: ignore[arg-type]
        status=RunStatus.CREATED.value,
        current=None,
        context=RunContext(inputs={}, step_executions={}),
        created_at="2026-03-10 10:00:00",
        updated_at="2026-03-10 10:00:00",
    )


def test_sets_current_to_start_when_unique_start_exists() -> None:
    store = _FakeStore(
        _build_run(
            {
                "start": "ask_user",
                "steps": [
                    {"notify": "ask_user", "message": "ok"},
                    {"notify": "done", "message": "done"},
                ]
            }
        )
    )
    use_case = GetStartStepUseCase(store=store)

    step_id = use_case.execute("run-1")

    assert step_id == "ask_user"
    assert store.updates == [
        {
            "run_id": "run-1",
            "status": None,
            "current": "ask_user",
            "context": None,
        }
    ]


@pytest.mark.parametrize(
    "snapshot",
    [
        {"steps": []},
        {"start": "start", "steps": [{"notify": "done"}]},
        {"start": "start", "steps": [{"notify": "start"}, {"notify": "start"}]},
        {"start": "start", "steps": []},
        {"steps": ["bad-step"]},
        [],
    ],
)
def test_rejects_invalid_start_config(snapshot: object) -> None:
    store = _FakeStore(_build_run(snapshot))
    use_case = GetStartStepUseCase(store=store)

    with pytest.raises(ValueError):
        use_case.execute("run-1")


def test_rejects_missing_run() -> None:
    use_case = GetStartStepUseCase(store=_FakeStore(None))

    with pytest.raises(ValueError, match="Run 'run-1' not found"):
        use_case.execute("run-1")
