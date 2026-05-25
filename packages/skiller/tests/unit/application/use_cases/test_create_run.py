import uuid

import pytest

from skiller.application.use_cases.run.create_run import CreateRunInput, CreateRunUseCase
from skiller.domain.run.run_context_model import RunContext

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []

    def create_run(
        self,
        source: str,
        ref: str,
        snapshot: dict[str, object],
        context: RunContext,
        *,
        run_id: str,
    ) -> str:
        self.create_calls.append(
            {
                "source": source,
                "ref": ref,
                "snapshot": snapshot,
                "context": context,
                "run_id": run_id,
            }
        )
        return run_id


class _FakeSkillRunner:
    def __init__(self, snapshot: object) -> None:
        self.snapshot = snapshot
        self.load_calls: list[tuple[str, str]] = []

    def load(self, source: str, ref: str) -> object:
        self.load_calls.append((source, ref))
        return self.snapshot


def test_create_run_generates_uuid_for_store() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner(
        {"start": "show_message", "steps": [{"notify": "show_message", "message": "ok"}]}
    )
    use_case = CreateRunUseCase(store=store, skill_runner=skill_runner)

    run_id = use_case.execute(
        CreateRunInput(skill_ref="notify_test", inputs={"message": "ok"})
    )

    assert str(uuid.UUID(run_id)) == run_id
    assert store.create_calls == [
        {
            "source": "internal",
            "ref": "notify_test",
            "snapshot": {
                "start": "show_message",
                "steps": [{"notify": "show_message", "message": "ok"}],
            },
            "context": RunContext(inputs={"message": "ok"}, step_executions={}),
            "run_id": run_id,
        }
    ]


def test_create_run_generates_uuid_when_called_without_inputs() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner(
        {"start": "show_message", "steps": [{"notify": "show_message", "message": "ok"}]}
    )
    use_case = CreateRunUseCase(store=store, skill_runner=skill_runner)

    run_id = use_case.execute(CreateRunInput(skill_ref="notify_test", inputs={}))

    assert run_id == store.create_calls[0]["run_id"]
    assert str(uuid.UUID(run_id)) == run_id


def test_create_run_rejects_invalid_skill_payload() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner(["bad-skill"])
    use_case = CreateRunUseCase(store=store, skill_runner=skill_runner)

    with pytest.raises(ValueError, match="Invalid skill format"):
        use_case.execute(CreateRunInput(skill_ref="notify_test", inputs={}))
