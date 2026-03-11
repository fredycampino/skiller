import pytest

from skiller.application.use_cases.execute_llm_prompt_step import ExecuteLlmPromptStepUseCase
from skiller.application.use_cases.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.step_execution_result import StepExecutionStatus
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus

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

    def append_event(self, event_type: str, payload: dict[str, object], run_id: str | None = None) -> str:
        self.events.append({"type": event_type, "payload": payload, "run_id": run_id})
        return "evt-1"


class _FakeLLM:
    def __init__(self, response: dict[str, object] | None = None) -> None:
        self.response = response or {"ok": True, "content": "{\"summary\":\"ok\",\"severity\":\"low\"}"}
        self.calls: list[dict[str, object]] = []

    def generate(self, messages: list[dict[str, str]], config: dict[str, object] | None = None) -> dict[str, object]:
        self.calls.append({"messages": messages, "config": config})
        return self.response


def test_execute_llm_prompt_step_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    llm = _FakeLLM()
    use_case = ExecuteLlmPromptStepUseCase(store=store, llm=llm)
    context = RunContext(inputs={"stderr": "boom"}, results={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=1,
            step_id="analyze_issue",
            step_type=StepType.LLM_PROMPT,
            step={
                "type": "llm_prompt",
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
    assert context.results["analyze_issue"] == {"summary": "ok", "severity": "low"}
    assert store.updated[0]["status"] == RunStatus.RUNNING
    assert store.updated[0]["current"] == "done"
    assert store.events[0]["type"] == "LLM_PROMPT_RESULT"
    assert store.events[0]["payload"]["step"] == "analyze_issue"


def test_execute_llm_prompt_step_preserves_prompt_whitespace() -> None:
    store = _FakeStore()
    llm = _FakeLLM(response={"ok": True, "content": '{"summary":"ok","severity":"low"}'})
    use_case = ExecuteLlmPromptStepUseCase(store=store, llm=llm)
    context = RunContext(inputs={}, results={})

    use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="analyze_issue",
            step_type=StepType.LLM_PROMPT,
            step={
                "type": "llm_prompt",
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
    use_case = ExecuteLlmPromptStepUseCase(store=store, llm=llm)
    context = RunContext(inputs={}, results={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="analyze_issue",
            step_type=StepType.LLM_PROMPT,
            step={
                "type": "llm_prompt",
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
    assert context.results["analyze_issue"] == {"summary": "ok", "severity": "low"}
    assert store.events[0]["type"] == "LLM_PROMPT_RESULT"


def test_execute_llm_prompt_step_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    llm = _FakeLLM()
    use_case = ExecuteLlmPromptStepUseCase(store=store, llm=llm)
    context = RunContext(inputs={"stderr": "boom"}, results={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="analyze_issue",
            step_type=StepType.LLM_PROMPT,
            step={
                "type": "llm_prompt",
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
    assert store.updated[0]["current"] is None


def test_execute_llm_prompt_step_rejects_empty_next_when_declared() -> None:
    store = _FakeStore()
    llm = _FakeLLM()
    use_case = ExecuteLlmPromptStepUseCase(store=store, llm=llm)
    context = RunContext(inputs={"stderr": "boom"}, results={})

    with pytest.raises(ValueError, match="requires non-empty next"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="analyze_issue",
                step_type=StepType.LLM_PROMPT,
                step={
                    "type": "llm_prompt",
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


def test_execute_llm_prompt_step_logs_raw_response_in_invalid_json_error() -> None:
    store = _FakeStore()
    llm = _FakeLLM(response={"ok": True, "content": "not-json", "model": "fake-llm"})
    use_case = ExecuteLlmPromptStepUseCase(store=store, llm=llm)
    context = RunContext(inputs={}, results={})

    with pytest.raises(ValueError, match="returned invalid JSON"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="analyze_issue",
                step_type=StepType.LLM_PROMPT,
                step={
                    "type": "llm_prompt",
                    "prompt": "Analyze",
                    "output": {
                        "format": "json",
                        "schema": {
                            "type": "object",
                            "required": ["summary"],
                            "properties": {"summary": {"type": "string"}},
                        },
                    },
                },
                context=context,
            )
        )

    assert store.events[0] == {
        "type": "LLM_PROMPT_ERROR",
        "payload": {
            "step": "analyze_issue",
            "error": "LLM step 'analyze_issue' returned invalid JSON: Expecting value",
            "model": "fake-llm",
            "raw_response": "not-json",
        },
        "run_id": "run-1",
    }


@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        ({"ok": False, "error": "provider down"}, "provider down"),
        ({"ok": True, "content": "not-json"}, "returned invalid JSON"),
        (
            {"ok": True, "content": "{\"summary\":\"ok\"}"},
            "required field is missing",
        ),
        (
            {"ok": True, "content": "{\"summary\":\"ok\",\"severity\":\"urgent\"}"},
            "value must be one of",
        ),
        (
            {"ok": True, "content": "{\"summary\":\"ok\",\"severity\":\"low\"}"},
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
    use_case = ExecuteLlmPromptStepUseCase(store=store, llm=llm)
    context = RunContext(inputs={}, results={})

    with pytest.raises(ValueError, match=expected_error):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="analyze_issue",
                step_type=StepType.LLM_PROMPT,
                step={
                    "type": "llm_prompt",
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
            {"type": "llm_prompt", "output": {"format": "json", "schema": {"type": "object"}}},
            "requires prompt",
        ),
        (
            {"type": "llm_prompt", "prompt": "Analyze"},
            "requires output object",
        ),
        (
            {"type": "llm_prompt", "prompt": "Analyze", "output": {"format": "text", "schema": {"type": "object"}}},
            "requires output.format 'json'",
        ),
        (
            {"type": "llm_prompt", "prompt": "Analyze", "output": {"format": "json"}},
            "requires output.schema object",
        ),
    ],
)
def test_execute_llm_prompt_step_validation_errors(step: dict[str, object], expected_error: str) -> None:
    use_case = ExecuteLlmPromptStepUseCase(store=_FakeStore(), llm=_FakeLLM())
    context = RunContext(inputs={}, results={})

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
