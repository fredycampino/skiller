from types import SimpleNamespace

import pytest

from skiller.application.use_cases.run.delete_run import DeleteRunStatus, DeleteRunUseCase

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, *, deleted: bool = True) -> None:
        self.deleted = deleted
        self.calls: list[str] = []

    def delete_run(self, run_id: str) -> bool:
        self.calls.append(run_id)
        return self.deleted

    def create_run(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return "run-1"

    def update_run(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def get_run(self, run_id: str):  # noqa: ANN201
        _ = run_id
        return SimpleNamespace(id="run-1")


def test_delete_run_deletes_normalized_run_id() -> None:
    store = _FakeStore()
    use_case = DeleteRunUseCase(store)

    result = use_case.execute(" run-1 ")

    assert result.status == DeleteRunStatus.DELETED
    assert result.run_id == "run-1"
    assert result.error is None
    assert store.calls == ["run-1"]


def test_delete_run_reports_missing_run() -> None:
    store = _FakeStore(deleted=False)
    use_case = DeleteRunUseCase(store)

    result = use_case.execute("run-1")

    assert result.status == DeleteRunStatus.RUN_NOT_FOUND
    assert result.run_id == "run-1"
    assert result.error == "Run 'run-1' not found"
    assert store.calls == ["run-1"]


def test_delete_run_rejects_empty_run_id() -> None:
    store = _FakeStore()
    use_case = DeleteRunUseCase(store)

    result = use_case.execute(" ")

    assert result.status == DeleteRunStatus.INVALID_RUN_ID
    assert result.run_id == " "
    assert result.error == "run_id is required"
    assert store.calls == []
