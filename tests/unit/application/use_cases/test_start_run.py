import uuid

import pytest

from skiller.application.use_cases.start_run import StartRunUseCase
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


def test_start_run_passes_trimmed_param_run_id_to_store() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner({"steps": [{"id": "start", "type": "notify", "message": "ok"}]})
    use_case = StartRunUseCase(store=store, skill_runner=skill_runner)
    raw_run_id = "550e8400-e29b-41d4-a716-446655440000"

    run_id = use_case.execute("notify_test", {"message": "ok"}, param_run_id=f"  {raw_run_id}  ")

    assert run_id == raw_run_id
    assert store.create_calls == [
        {
            "skill_source": "internal",
            "skill_ref": "notify_test",
            "skill_snapshot": {"steps": [{"id": "start", "type": "notify", "message": "ok"}]},
            "context": RunContext(inputs={"message": "ok"}, results={}),
            "run_id": raw_run_id,
        }
    ]


def test_start_run_generates_uuid_when_param_run_id_is_missing() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner({"steps": [{"id": "start", "type": "notify", "message": "ok"}]})
    use_case = StartRunUseCase(store=store, skill_runner=skill_runner)

    run_id = use_case.execute("notify_test", {})

    assert run_id == store.create_calls[0]["run_id"]
    assert str(uuid.UUID(run_id)) == run_id


def test_start_run_rejects_blank_param_run_id() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner({"steps": [{"id": "start", "type": "notify", "message": "ok"}]})
    use_case = StartRunUseCase(store=store, skill_runner=skill_runner)

    with pytest.raises(ValueError, match="Run id must be a non-empty string"):
        use_case.execute("notify_test", {}, param_run_id="   ")


def test_start_run_rejects_non_uuid_param_run_id() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner({"steps": [{"id": "start", "type": "notify", "message": "ok"}]})
    use_case = StartRunUseCase(store=store, skill_runner=skill_runner)

    with pytest.raises(ValueError, match="Run id must be a valid UUID"):
        use_case.execute("notify_test", {}, param_run_id="run-ui-123")


def test_start_run_rejects_invalid_skill_payload() -> None:
    store = _FakeStore()
    skill_runner = _FakeSkillRunner(["bad-skill"])
    use_case = StartRunUseCase(store=store, skill_runner=skill_runner)

    with pytest.raises(ValueError, match="Invalid skill format"):
        use_case.execute("notify_test", {})
