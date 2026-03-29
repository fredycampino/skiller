import pytest

from skiller.application.use_cases.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.step_execution_result import StepExecutionStatus
from skiller.domain.large_result_truncator import LargeResultTruncator
from skiller.domain.mcp_config_model import RenderedMcpConfig
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import McpOutput

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

    def append_event(
        self, event_type: str, payload: dict[str, object], run_id: str | None = None
    ) -> str:
        self.events.append({"type": event_type, "payload": payload, "run_id": run_id})
        return "evt-1"


class _FakeMCP:
    def __init__(self, *, result: dict[str, object] | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.result = result or {"ok": True}

    def connect(self, server_name: str) -> dict[str, object]:
        return {"ok": True, "server": server_name}

    def probe(self, server_name: str) -> dict[str, object]:
        return {"ok": True, "server": server_name}

    def list_tools(self, server_name: str) -> list[str]:
        return []

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        args: dict[str, object],
        config: RenderedMcpConfig | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {"server": server_name, "tool": tool_name, "args": args, "config": config}
        )
        return {
            "server": server_name,
            "tool": tool_name,
            "args": args,
            **self.result,
        }

    def read_resource(self, server_name: str, uri: str) -> dict[str, object]:
        return {"ok": True, "server": server_name, "uri": uri}


class _FakeExecutionOutputStore:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def store_execution_output(
        self,
        *,
        run_id: str,
        step_id: str,
        output_body: dict[str, object],
    ) -> str:
        self.calls.append(
            {
                "run_id": run_id,
                "step_id": step_id,
                "output_body": output_body,
            }
        )
        return "execution_output:1"

    def get_execution_output(self, body_ref: str) -> dict[str, object] | None:
        _ = body_ref
        return None


def test_execute_mcp_step_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    execution_output_store = _FakeExecutionOutputStore()
    mcp = _FakeMCP()
    use_case = ExecuteMcpStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        mcp=mcp,
        large_result_truncator=LargeResultTruncator(),
    )

    context = RunContext(inputs={}, step_executions={})
    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=2,
            step_id="open_example",
            step_type=StepType.MCP,
            step={
                "server": "chrome-mcp",
                "tool": "navigate_page",
                "args": {"url": "https://example.com"},
                "next": "done",
            },
            context=context,
        ),
        RenderedMcpConfig(name="chrome-mcp", transport="stdio", command="/usr/bin/python3"),
    )

    assert result.status == StepExecutionStatus.NEXT
    assert result.next_step_id == "done"
    assert result.execution is not None
    assert result.execution.output == McpOutput(
        text="chrome-mcp.navigate_page completed successfully.",
        data={
            "server": "chrome-mcp",
            "tool": "navigate_page",
            "args": {"url": "https://example.com"},
            "ok": True,
        },
    )
    assert mcp.calls == [
        {
            "server": "chrome-mcp",
            "tool": "navigate_page",
            "args": {"url": "https://example.com"},
            "config": RenderedMcpConfig(
                name="chrome-mcp", transport="stdio", command="/usr/bin/python3"
            ),
        }
    ]
    assert context.step_executions["open_example"] == result.execution
    assert store.updated[0]["run_id"] == "run-1"
    assert store.updated[0]["status"] == RunStatus.RUNNING
    assert store.updated[0]["current"] == "done"
    assert store.events == []
    assert execution_output_store.calls == []


def test_execute_mcp_step_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    execution_output_store = _FakeExecutionOutputStore()
    mcp = _FakeMCP()
    use_case = ExecuteMcpStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        mcp=mcp,
        large_result_truncator=LargeResultTruncator(),
    )
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=2,
            step_id="open_example",
            step_type=StepType.MCP,
            step={
                "server": "chrome-mcp",
                "tool": "navigate_page",
                "args": {"url": "https://example.com"},
            },
            context=context,
        ),
        RenderedMcpConfig(name="chrome-mcp", transport="stdio", command="/usr/bin/python3"),
    )

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert result.execution is not None
    assert result.execution.output == McpOutput(
        text="chrome-mcp.navigate_page completed successfully.",
        data={
            "server": "chrome-mcp",
            "tool": "navigate_page",
            "args": {"url": "https://example.com"},
            "ok": True,
        },
    )
    assert store.updated[0]["current"] is None
    assert execution_output_store.calls == []


def test_execute_mcp_step_raises_and_does_not_advance_on_mcp_error() -> None:
    store = _FakeStore()
    execution_output_store = _FakeExecutionOutputStore()
    mcp = _FakeMCP(result={"ok": False, "error": "Access denied"})
    use_case = ExecuteMcpStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        mcp=mcp,
        large_result_truncator=LargeResultTruncator(),
    )
    context = RunContext(inputs={}, step_executions={})

    with pytest.raises(ValueError, match="Access denied"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=2,
                step_id="create_file",
                step_type=StepType.MCP,
                step={
                    "server": "local-mcp",
                    "tool": "files_action",
                    "args": {"action": "create", "path": "/tmp/demo.txt", "content": "hola"},
                },
                context=context,
            ),
            RenderedMcpConfig(name="local-mcp", transport="stdio", command="/usr/bin/python3"),
        )

    assert store.updated == []
    assert store.events == []
    assert context.step_executions == {}
    assert execution_output_store.calls == []


def test_execute_mcp_step_persists_large_result_body_and_truncates_output_value() -> None:
    store = _FakeStore()
    execution_output_store = _FakeExecutionOutputStore()
    mcp = _FakeMCP(
        result={
            "ok": True,
            "total": 248,
            "items": [{"id": "a1"}, {"id": "a2"}],
            "meta": {"source": "search", "region": "eu"},
        }
    )
    use_case = ExecuteMcpStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        mcp=mcp,
        large_result_truncator=LargeResultTruncator(),
    )
    context = RunContext(inputs={}, step_executions={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=2,
            step_id="search",
            step_type=StepType.MCP,
            step={
                "server": "local-mcp",
                "tool": "search",
                "args": {"query": "auth"},
                "large_result": True,
                "next": "done",
            },
            context=context,
        ),
        RenderedMcpConfig(name="local-mcp", transport="stdio", command="/usr/bin/python3"),
    )

    assert result.execution is not None
    assert result.execution.output == McpOutput(
        text="local-mcp.search completed successfully.",
        data={
            "truncated": True,
            "server": "local-mcp",
            "tool": "search",
            "args_keys": ["query"],
            "ok": True,
            "total": 248,
            "items_count": 2,
            "meta_keys": ["region", "source"],
        },
        body_ref="execution_output:1",
    )
    assert execution_output_store.calls == [
        {
            "run_id": "run-1",
            "step_id": "search",
            "output_body": {
                "server": "local-mcp",
                "tool": "search",
                "args": {"query": "auth"},
                "ok": True,
                "total": 248,
                "items": [{"id": "a1"}, {"id": "a2"}],
                "meta": {"source": "search", "region": "eu"},
            },
        }
    ]


@pytest.mark.parametrize(
    "step,expected_error",
    [
        ({"tool": "navigate_page", "args": {}}, "requires mcp server name"),
        ({"server": "chrome-mcp", "args": {}}, "requires tool name"),
        (
            {
                "server": "chrome-mcp",
                "tool": "mcp.chrome-mcp.navigate_page",
                "args": {},
            },
            "plain tool name",
        ),
        (
            {"server": "chrome-mcp", "tool": "navigate_page", "args": "not-a-dict"},
            "args must be an object",
        ),
        (
            {
                "server": "chrome-mcp",
                "tool": "navigate_page",
                "args": {},
                "next": "   ",
            },
            "requires non-empty next",
        ),
    ],
)
def test_execute_mcp_step_validation_errors(step: dict[str, object], expected_error: str) -> None:
    use_case = ExecuteMcpStepUseCase(
        store=_FakeStore(),
        execution_output_store=_FakeExecutionOutputStore(),
        mcp=_FakeMCP(),
        large_result_truncator=LargeResultTruncator(),
    )
    context = RunContext(inputs={}, step_executions={})

    with pytest.raises(ValueError, match=expected_error):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=0,
                step_id="bad_step",
                step_type=StepType.MCP,
                step=step,
                context=context,
            ),
            RenderedMcpConfig(name="chrome-mcp", transport="stdio", command="/usr/bin/python3"),
        )
