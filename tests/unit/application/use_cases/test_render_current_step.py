import pytest

from skiller.application.use_cases.render_current_step import RenderCurrentStepUseCase, CurrentStepStatus, StepType
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import Run, RunStatus

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self, run: Run | None) -> None:
        self._run = run

    def get_run(self, run_id: str) -> Run | None:
        _ = run_id
        return self._run


class _FakeSkillRunner:
    def __init__(self, skill: object) -> None:
        self._skill = skill
        self.render_calls: list[dict[str, object]] = []
        self.load_calls: list[tuple[str, str]] = []

    def load_skill(self, skill_source: str, skill_ref: str):  # noqa: ANN202
        self.load_calls.append((skill_source, skill_ref))
        return self._skill

    def render_step(self, step: dict[str, object], context: dict[str, object]) -> dict[str, object]:
        self.render_calls.append({"step": step, "context": context})
        rendered = dict(step)
        rendered["rendered"] = True
        return rendered


def _build_run(
    *,
    status: str = RunStatus.CREATED.value,
    current: str | None = "start",
    skill_snapshot: object | None = None,
) -> Run:
    return Run(
        id="run-1",
        skill_source="internal",
        skill_ref="demo",
        skill_snapshot=skill_snapshot if skill_snapshot is not None else {"steps": [{"id": "start", "type": "notify"}]},
        status=status,
        current=current,
        context=RunContext(inputs={"repo": "acme"}, results={"prev": {"ok": True}}),
        created_at="2026-03-07 10:00:00",
        updated_at="2026-03-07 10:00:00",
    )


def test_returns_run_not_found_when_missing() -> None:
    use_case = RenderCurrentStepUseCase(
        store=_FakeStore(None),
        skill_runner=_FakeSkillRunner({"steps": []}),
    )

    result = use_case.execute("missing")

    assert result.status == CurrentStepStatus.RUN_NOT_FOUND
    assert result.current_step is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (RunStatus.CANCELLED.value, CurrentStepStatus.CANCELLED),
        (RunStatus.WAITING.value, CurrentStepStatus.WAITING),
    ],
)
def test_blocks_when_run_is_not_executable(status: str, expected: CurrentStepStatus) -> None:
    run = _build_run(status=status)
    use_case = RenderCurrentStepUseCase(
        store=_FakeStore(run),
        skill_runner=_FakeSkillRunner({"steps": []}),
    )

    result = use_case.execute("run-1")

    assert result.status == expected
    assert result.current_step is None


def test_returns_invalid_skill_when_current_is_missing() -> None:
    run = _build_run(current=None)
    use_case = RenderCurrentStepUseCase(store=_FakeStore(run), skill_runner=_FakeSkillRunner({"steps": []}))

    result = use_case.execute("run-1")

    assert result.status == CurrentStepStatus.INVALID_SKILL
    assert result.current_step is None


def test_returns_ready_with_rendered_step() -> None:
    run = _build_run(current="s2")
    run.skill_snapshot = {"steps": [{"id": "start"}, {"id": "s2", "type": "mcp"}]}
    skill_runner = _FakeSkillRunner({"steps": [{"id": "ignored"}]})
    use_case = RenderCurrentStepUseCase(store=_FakeStore(run), skill_runner=skill_runner)

    result = use_case.execute("run-1")

    assert result.status == CurrentStepStatus.READY
    assert result.current_step is not None
    assert result.current_step.step_index == 1
    assert result.current_step.step_id == "s2"
    assert result.current_step.step_type == StepType.MCP
    assert result.current_step.context == run.context
    assert result.current_step.step["rendered"] is True
    assert skill_runner.render_calls[0]["context"] == run.context.to_dict()
    assert skill_runner.load_calls == []


def test_returns_ready_with_llm_prompt_step_type() -> None:
    run = _build_run(current="analyze")
    run.skill_snapshot = {"steps": [{"id": "analyze", "type": "llm_prompt", "prompt": "hello"}]}
    use_case = RenderCurrentStepUseCase(store=_FakeStore(run), skill_runner=_FakeSkillRunner({"steps": []}))

    result = use_case.execute("run-1")

    assert result.status == CurrentStepStatus.READY
    assert result.current_step is not None
    assert result.current_step.step_type == StepType.LLM_PROMPT


def test_returns_ready_with_assign_step_type() -> None:
    run = _build_run(current="prepare")
    run.skill_snapshot = {"steps": [{"id": "prepare", "type": "assign", "values": {"action": "retry"}}]}
    use_case = RenderCurrentStepUseCase(store=_FakeStore(run), skill_runner=_FakeSkillRunner({"steps": []}))

    result = use_case.execute("run-1")

    assert result.status == CurrentStepStatus.READY
    assert result.current_step is not None
    assert result.current_step.step_type == StepType.ASSIGN


def test_returns_ready_with_switch_step_type() -> None:
    run = _build_run(current="decide")
    run.skill_snapshot = {
        "steps": [
            {
                "id": "decide",
                "type": "switch",
                "value": "{{results.start.action}}",
                "cases": {"retry": "retry_notice"},
                "default": "unknown_action",
            }
        ]
    }
    use_case = RenderCurrentStepUseCase(store=_FakeStore(run), skill_runner=_FakeSkillRunner({"steps": []}))

    result = use_case.execute("run-1")

    assert result.status == CurrentStepStatus.READY
    assert result.current_step is not None
    assert result.current_step.step_type == StepType.SWITCH


def test_returns_ready_with_when_step_type() -> None:
    run = _build_run(current="decide")
    run.skill_snapshot = {
        "steps": [
            {
                "id": "decide",
                "type": "when",
                "value": "{{results.score}}",
                "branches": [{"gt": 90, "then": "excellent"}],
                "default": "fail",
            }
        ]
    }
    use_case = RenderCurrentStepUseCase(store=_FakeStore(run), skill_runner=_FakeSkillRunner({"steps": []}))

    result = use_case.execute("run-1")

    assert result.status == CurrentStepStatus.READY
    assert result.current_step is not None
    assert result.current_step.step_type == StepType.WHEN


def test_returns_invalid_skill_when_skill_shape_is_wrong() -> None:
    run = _build_run(skill_snapshot=[])  # type: ignore[arg-type]
    use_case = RenderCurrentStepUseCase(
        store=_FakeStore(run),
        skill_runner=_FakeSkillRunner(["not-a-dict"]),
    )

    result = use_case.execute("run-1")

    assert result.status == CurrentStepStatus.INVALID_SKILL
    assert result.current_step is None


def test_returns_invalid_skill_when_current_id_does_not_exist() -> None:
    run = _build_run(current="missing")
    run.skill_snapshot = {"steps": [{"id": "start", "type": "notify"}]}
    use_case = RenderCurrentStepUseCase(store=_FakeStore(run), skill_runner=_FakeSkillRunner({"steps": []}))

    result = use_case.execute("run-1")

    assert result.status == CurrentStepStatus.INVALID_SKILL
    assert result.current_step is None
