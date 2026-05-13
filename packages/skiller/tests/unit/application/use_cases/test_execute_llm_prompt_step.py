import pytest

from skiller.application.use_cases.execute.execute_llm_prompt_step import (
    ExecuteLlmPromptStepUseCase,
)
from skiller.application.use_cases.render.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.shared.step_execution_result import StepExecutionStatus
from skiller.domain.event.event_model import RuntimeEventDraft
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_execution_model import LlmPromptOutput

pytestmark = pytest.mark.unit


class _FakeStore:
    def __init__(self) -> None:
        self.updated: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []

    def update_run(self, run_id: str, *, status=None, current=None, context=None) -> None:  # noqa: ANN001
        self.updated.append(
            {
                "run_id": run_id,
                "status": status,
                "current": current,
                "context": context,
            }
        )

    def append_event(self, event: RuntimeEventDraft) -> str:
        self.events.append(
            {"type": event.type.value, "payload": event.payload, "run_id": event.run_id}
        )
        return "evt-1"


class _FakeLLM:
    def __init__(self, response: dict[str, object] | None = None) -> None:
        self.response = response or {"ok": True, "content": '{"summary":"ok","severity":"low"}'}
        self.calls: list[dict[str, object]] = []

    def generate(
        self, messages: list[dict[str, str]], config: dict[str, object] | None = None
    ) -> dict[str, object]:
        self.calls.append({"messages": messages, "config": config})
        return self.response


def _build_use_case(
    *,
    store: _FakeStore | None = None,
    llm: _FakeLLM | None = None,
) -> ExecuteLlmPromptStepUseCase:
    return ExecuteLlmPromptStepUseCase(
        store=store or _FakeStore(),
        llm=llm or _FakeLLM(),
    )


def test_execute_llm_prompt_step_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    llm = _FakeLLM()
    use_case = _build_use_case(store=store, llm=llm)
    context = RunContext(inputs={"stderr": "boom"}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=1,
            step_id="analyze_issue",
            step_type=StepType.LLM_PROMPT,
            step={
                "system": "Return JSON.",
                "prompt": "Analyze {{inputs.stderr}}",
                "next": "done",
                "output": {
                    "format": "json",
                    "schema": {
                        "type": "object",
                        "required": ["summary", "severity"],
                        "properties": {
                            "summary": {"type": "string"},
                            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        },
                    },
                },
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == LlmPromptOutput(
        text='{"severity": "low", "summary": "ok"}',
        data={"summary": "ok", "severity": "low"},
    )
    assert llm.calls == [
        {
            "messages": [
                {"role": "system", "content": "Return JSON."},
                {"role": "user", "content": "Analyze {{inputs.stderr}}"},
            ],
            "config": {
                "output": {
                    "format": "json",
                    "schema": {
                        "type": "object",
                        "required": ["summary", "severity"],
                        "properties": {
                            "summary": {"type": "string"},
                            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        },
                    },
                },
                "step_id": "analyze_issue",
            },
        }
    ]
    assert context.step_executions["analyze_issue"] == result.execution
    assert result.execution.evaluation == {"model": None}
    assert store.updated[0]["status"] == RunStatus.RUNNING
    assert store.updated[0]["current"] == "done"
    assert store.events == []


def test_execute_llm_prompt_step_preserves_prompt_whitespace() -> None:
    store = _FakeStore()
    llm = _FakeLLM(response={"ok": True, "content": '{"summary":"ok","severity":"low"}'})
    use_case = _build_use_case(store=store, llm=llm)
    context = RunContext(inputs={}, step_executions={})

    use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="analyze_issue",
            step_type=StepType.LLM_PROMPT,
            step={
                "system": "Return JSON.\n",
                "prompt": "Analyze this.\n\n",
                "output": {
                    "format": "json",
                    "schema": {
                        "type": "object",
                        "required": ["summary", "severity"],
                        "properties": {
                            "summary": {"type": "string"},
                            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        },
                    },
                },
            },
            context=context,
        )
    )

    assert llm.calls[0]["messages"] == [
        {"role": "system", "content": "Return JSON.\n"},
        {"role": "user", "content": "Analyze this.\n\n"},
    ]


def test_execute_llm_prompt_step_accepts_json_inside_markdown_fence() -> None:
    store = _FakeStore()
    llm = _FakeLLM(
        response={
            "ok": True,
            "content": '```json\n{"summary":"ok","severity":"low"}\n```',
            "model": "fake-llm",
        }
    )
    use_case = _build_use_case(store=store, llm=llm)
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="analyze_issue",
            step_type=StepType.LLM_PROMPT,
            step={
                "prompt": "Analyze",
                "next": "done",
                "output": {
                    "format": "json",
                    "schema": {
                        "type": "object",
                        "required": ["summary", "severity"],
                        "properties": {
                            "summary": {"type": "string"},
                            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        },
                    },
                },
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == LlmPromptOutput(
        text='{"severity": "low", "summary": "ok"}',
        data={"summary": "ok", "severity": "low"},
    )
    assert context.step_executions["analyze_issue"] == result.execution
    assert result.execution.evaluation == {"model": "fake-llm"}
    assert store.events == []


def test_execute_llm_prompt_step_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    llm = _FakeLLM()
    use_case = _build_use_case(store=store, llm=llm)
    context = RunContext(inputs={"stderr": "boom"}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="analyze_issue",
            step_type=StepType.LLM_PROMPT,
            step={
                "prompt": "Analyze {{inputs.stderr}}",
                "output": {
                    "format": "json",
                    "schema": {
                        "type": "object",
                        "required": ["summary", "severity"],
                        "properties": {
                            "summary": {"type": "string"},
                            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        },
                    },
                },
            },
            context=context,
        )
    )

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert result.execution is not None
    assert result.execution.output == LlmPromptOutput(
        text='{"severity": "low", "summary": "ok"}',
        data={"summary": "ok", "severity": "low"},
    )
    assert store.updated[0]["current"] is None


def test_execute_llm_prompt_step_rejects_empty_next_when_declared() -> None:
    store = _FakeStore()
    llm = _FakeLLM()
    use_case = _build_use_case(store=store, llm=llm)
    context = RunContext(inputs={"stderr": "boom"}, step_executions={})

    with pytest.raises(ValueError, match="requires non-empty next"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="analyze_issue",
                step_type=StepType.LLM_PROMPT,
                step={
                    "prompt": "Analyze {{inputs.stderr}}",
                    "next": "   ",
                    "output": {
                        "format": "json",
                        "schema": {
                            "type": "object",
                            "required": ["summary", "severity"],
                            "properties": {
                                "summary": {"type": "string"},
                                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                            },
                        },
                    },
                },
                context=context,
            )
        )

@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        ({"ok": False, "error": "provider down"}, "provider down"),
        ({"ok": True, "content": "not-json"}, "returned invalid JSON"),
        (
            {"ok": True, "content": '{"summary":"ok"}'},
            "required field is missing",
        ),
        (
            {"ok": True, "content": '{"summary":"ok","severity":"urgent"}'},
            "value must be one of",
        ),
        (
            {"ok": True, "content": '{"summary":"ok","severity":"low"}'},
            "unsupported type",
        ),
    ],
)
def test_execute_llm_prompt_step_fails_on_invalid_provider_output(
    response: dict[str, object],
    expected_error: str,
) -> None:
    store = _FakeStore()
    llm = _FakeLLM(response=response)
    use_case = _build_use_case(store=store, llm=llm)
    context = RunContext(inputs={}, step_executions={})

    with pytest.raises(ValueError, match=expected_error):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="analyze_issue",
                step_type=StepType.LLM_PROMPT,
                step={
                    "prompt": "Analyze",
                    "output": {
                        "format": "json",
                        "schema": {
                            "type": "unknown" if expected_error == "unsupported type" else "object",
                            "required": ["summary", "severity"],
                            "properties": {
                                "summary": {"type": "string"},
                                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                            },
                        },
                    },
                },
                context=context,
            )
        )

    assert store.updated == []


@pytest.mark.parametrize(
    ("step", "expected_error"),
    [
        (
            {"output": {"format": "json", "schema": {"type": "object"}}},
            "requires prompt",
        ),
        (
            {"prompt": "Analyze"},
            "requires output object",
        ),
        (
            {
                "prompt": "Analyze",
                "output": {"format": "text", "schema": {"type": "object"}},
            },
            "requires output.format 'json'",
        ),
        (
            {"prompt": "Analyze", "output": {"format": "json"}},
            "requires output.schema object",
        ),
    ],
)
def test_execute_llm_prompt_step_validation_errors(
    step: dict[str, object], expected_error: str
) -> None:
    use_case = _build_use_case()
    context = RunContext(inputs={}, step_executions={})

    with pytest.raises(ValueError, match=expected_error):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="bad_llm_step",
                step_type=StepType.LLM_PROMPT,
                step=step,
                context=context,
            )
        )
