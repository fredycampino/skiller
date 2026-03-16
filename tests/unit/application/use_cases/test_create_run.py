import uuid

import pytest

from skiller.application.use_cases.create_run import CreateRunUseCase
from skiller.domain.run_context_model import RunContext

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []

    def create_run(
        self,
        skill_source: str,
        skill_ref: str,
        skill_snapshot: dict[str, object],
        context: RunContext,
        *,
        run_id: str,
    ) -> str:
        self.create_calls.append(
            {
                "skill_source": skill_source,
                "skill_ref": skill_ref,
                "skill_snapshot": skill_snapshot,
                "context": context,
                "run_id": run_id,
            }
        )
        return run_id


class _FakeSkillRunner:
    def __init__(self, skill_snapshot: object) -> None:
        self.skill_snapshot = skill_snapshot
        self.load_calls: list[tuple[str, str]] = []

    def load_skill(self, skill_source: str, skill_ref: str) -> object:
        self.load_calls.append((skill_source, skill_ref))
        return self.skill_snapshot


def test_create_run_generates_uuid_for_store() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner({"steps": [{"id": "start", "type": "notify", "message": "ok"}]})
    use_case = CreateRunUseCase(store=store, skill_runner=skill_runner)

    run_id = use_case.execute("notify_test", {"message": "ok"})

    assert str(uuid.UUID(run_id)) == run_id
    assert store.create_calls == [
        {
            "skill_source": "internal",
            "skill_ref": "notify_test",
            "skill_snapshot": {"steps": [{"id": "start", "type": "notify", "message": "ok"}]},
            "context": RunContext(inputs={"message": "ok"}, results={}),
            "run_id": run_id,
        }
    ]


def test_create_run_generates_uuid_when_called_without_inputs() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner({"steps": [{"id": "start", "type": "notify", "message": "ok"}]})
    use_case = CreateRunUseCase(store=store, skill_runner=skill_runner)

    run_id = use_case.execute("notify_test", {})

    assert run_id == store.create_calls[0]["run_id"]
    assert str(uuid.UUID(run_id)) == run_id


def test_create_run_rejects_invalid_skill_payload() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner(["bad-skill"])
    use_case = CreateRunUseCase(store=store, skill_runner=skill_runner)

    with pytest.raises(ValueError, match="Invalid skill format"):
        use_case.execute("notify_test", {})
