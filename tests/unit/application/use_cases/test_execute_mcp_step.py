import pytest

from skiller.application.use_cases.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.step_execution_result import StepExecutionStatus
from skiller.domain.mcp_config_model import RenderedMcpConfig
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


def test_execute_mcp_step_moves_current_to_explicit_next() -> None:
    store = _FakeStore()
    mcp = _FakeMCP()
    use_case = ExecuteMcpStepUseCase(store=store, mcp=mcp)

    context = RunContext(inputs={}, results={})
    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=2,
            step_id="open_example",
            step_type=StepType.MCP,
            step={
                "type": "mcp",
                "mcp": "chrome-mcp",
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
    assert context.results["open_example"]["ok"] is True
    assert store.updated[0]["run_id"] == "run-1"
    assert store.updated[0]["status"] == RunStatus.RUNNING
    assert store.updated[0]["current"] == "done"
    assert store.events[0]["type"] == "MCP_RESULT"
    assert store.events[0]["run_id"] == "run-1"
    assert store.events[0]["payload"]["mcp"] == "chrome-mcp"


def test_execute_mcp_step_marks_completed_when_next_is_missing() -> None:
    store = _FakeStore()
    mcp = _FakeMCP()
    use_case = ExecuteMcpStepUseCase(store=store, mcp=mcp)
    context = RunContext(inputs={}, results={})

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=2,
            step_id="open_example",
            step_type=StepType.MCP,
            step={
                "type": "mcp",
                "mcp": "chrome-mcp",
                "tool": "navigate_page",
                "args": {"url": "https://example.com"},
            },
            context=context,
        ),
        RenderedMcpConfig(name="chrome-mcp", transport="stdio", command="/usr/bin/python3"),
    )

    assert result.status == StepExecutionStatus.COMPLETED
    assert result.next_step_id is None
    assert store.updated[0]["current"] is None


def test_execute_mcp_step_raises_and_does_not_advance_on_mcp_error() -> None:
    store = _FakeStore()
    mcp = _FakeMCP(result={"ok": False, "error": "Access denied"})
    use_case = ExecuteMcpStepUseCase(store=store, mcp=mcp)
    context = RunContext(inputs={}, results={})

    with pytest.raises(ValueError, match="Access denied"):
        use_case.execute(
            CurrentStep(
                run_id="run-1",
                step_index=2,
                step_id="create_file",
                step_type=StepType.MCP,
                step={
                    "type": "mcp",
                    "mcp": "local-mcp",
                    "tool": "files_action",
                    "args": {"action": "create", "path": "/tmp/demo.txt", "content": "hola"},
                },
                context=context,
            ),
            RenderedMcpConfig(name="local-mcp", transport="stdio", command="/usr/bin/python3"),
        )

    assert store.updated == []
    assert store.events[0]["type"] == "MCP_RESULT"
    assert store.events[0]["payload"]["result"]["ok"] is False
    assert context.results["create_file"]["ok"] is False


@pytest.mark.parametrize(
    "step,expected_error",
    [
        ({"type": "mcp", "tool": "navigate_page", "args": {}}, "requires mcp server name"),
        ({"type": "mcp", "mcp": "chrome-mcp", "args": {}}, "requires tool name"),
        (
            {
                "type": "mcp",
                "mcp": "chrome-mcp",
                "tool": "mcp.chrome-mcp.navigate_page",
                "args": {},
            },
            "plain tool name",
        ),
        (
            {"type": "mcp", "mcp": "chrome-mcp", "tool": "navigate_page", "args": "not-a-dict"},
            "args must be an object",
        ),
        (
            {
                "type": "mcp",
                "mcp": "chrome-mcp",
                "tool": "navigate_page",
                "args": {},
                "next": "   ",
            },
            "requires non-empty next",
        ),
    ],
)
def test_execute_mcp_step_validation_errors(step: dict[str, object], expected_error: str) -> None:
    use_case = ExecuteMcpStepUseCase(store=_FakeStore(), mcp=_FakeMCP())
    context = RunContext(inputs={}, results={})

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
