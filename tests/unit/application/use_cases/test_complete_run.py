import pytest

from skiller.application.use_cases.complete_run import CompleteRunUseCase
from skiller.domain.run_model import RunStatus

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        context: object | None = None,
    ) -> None:
        self.updates.append(
            {
                "run_id": run_id,
                "status": status,
                "context": context,
            }
        )

def test_complete_run_marks_succeeded() -> None:
    store = _FakeStore()
    use_case = CompleteRunUseCase(store)

    use_case.execute("run-1")

    assert store.updates == [
        {
            "run_id": "run-1",
            "status": RunStatus.SUCCEEDED,
            "context": None,
        }
    ]
