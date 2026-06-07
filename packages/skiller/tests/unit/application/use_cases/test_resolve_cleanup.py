import pytest

from skiller.application.use_cases.run.resolve_cleanup import (
    ResolveCleanupInput,
    ResolveCleanupUseCase,
)
from skiller.domain.action.action_model import EndActionTrigger
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import Run, RunStatus

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: Run | None, *, cleaned: bool = True) -> None:
        self.run = run
        self.cleaned = cleaned
        self.cleanup_run_ids: list[str] = []

    def get_run(self, run_id: str) -> Run | None:
        if self.run is None or self.run.id != run_id:
            return None
        return self.run

    def cleanup_run(self, run_id: str) -> bool:
        self.cleanup_run_ids.append(run_id)
        return self.cleaned


def test_resolve_cleanup_runs_cleanup_when_trigger_enables_it() -> None:
    store = _FakeStore(_build_run({"on_success": {"cleanup": True}}))
    use_case = ResolveCleanupUseCase(store)

    result = use_case.execute(
        ResolveCleanupInput(run_id="run-1", trigger=EndActionTrigger.ON_SUCCESS)
    )

    assert result.cleanup is True
    assert result.cleaned is True
    assert store.cleanup_run_ids == ["run-1"]


def test_resolve_cleanup_ignores_missing_cleanup_flag() -> None:
    store = _FakeStore(_build_run({"on_success": {"cleanup": False}}))
    use_case = ResolveCleanupUseCase(store)

    result = use_case.execute(
        ResolveCleanupInput(run_id="run-1", trigger=EndActionTrigger.ON_SUCCESS)
    )

    assert result.cleanup is False
    assert result.cleaned is False
    assert store.cleanup_run_ids == []


def test_resolve_cleanup_ignores_missing_run() -> None:
    store = _FakeStore(None)
    use_case = ResolveCleanupUseCase(store)

    result = use_case.execute(
        ResolveCleanupInput(run_id="missing", trigger=EndActionTrigger.ON_ERROR)
    )

    assert result.cleanup is False
    assert result.cleaned is False
    assert store.cleanup_run_ids == []


def _build_run(snapshot: dict[str, object]) -> Run:
    return Run(
        id="run-1",
        source="internal",
        ref="test",
        snapshot=snapshot,
        status=RunStatus.SUCCEEDED.value,
        current=None,
        context=RunContext(inputs={}, step_executions={}),
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
