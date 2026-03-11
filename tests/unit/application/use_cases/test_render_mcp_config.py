import pytest
import re

from skiller.application.use_cases.render_current_step import CurrentStep, StepType
from skiller.application.use_cases.render_mcp_config import (
    RenderMcpConfigStatus,
    RenderMcpConfigUseCase,
)
from skiller.domain.mcp_config_model import RenderedMcpConfig
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import Run

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
        return self._render_value(dict(step), context)

    def _render_value(self, value: object, context: dict[str, object]) -> object:
        if isinstance(value, dict):
            return {key: self._render_value(item, context) for key, item in value.items()}
        if isinstance(value, list):
            return [self._render_value(item, context) for item in value]
        if isinstance(value, str):
            return re.sub(
                r"\{\{\s*inputs\.([a-zA-Z0-9_]+)\s*\}\}",
                lambda match: str(context["inputs"].get(match.group(1), match.group(0))),
                value,
            )
        return value


def _build_run(skill_snapshot: dict[str, object] | None = None) -> Run:
    return Run(
        id="run-1",
        skill_source="internal",
        skill_ref="local_mcp",
        skill_snapshot=skill_snapshot
        or {
            "mcp": [
                {
                    "name": "local-mcp",
                    "transport": "stdio",
                    "command": "/usr/bin/python3",
                }
            ]
        },
        status="CREATED",
        current="start",
        context=RunContext(inputs={"root": "/tmp/work"}, results={}),
        created_at="2026-03-07 10:00:00",
        updated_at="2026-03-07 10:00:00",
    )


def _build_run_with_inputs(*, skill_snapshot: dict[str, object] | None = None, **inputs: str) -> Run:
    return Run(
        id="run-1",
        skill_source="internal",
        skill_ref="local_mcp",
        skill_snapshot=skill_snapshot
        or {
            "mcp": [
                {
                    "name": "local-mcp",
                    "transport": "stdio",
                    "command": "/usr/bin/python3",
                }
            ]
        },
        status="CREATED",
        current="start",
        context=RunContext(inputs=inputs, results={}),
        created_at="2026-03-07 10:00:00",
        updated_at="2026-03-07 10:00:00",
    )


def test_render_mcp_config_returns_rendered_stdio_config() -> None:
    skill_snapshot = {
        "mcp": [
            {
                "name": "local-mcp",
                "transport": "stdio",
                "command": "/usr/bin/python3",
                "args": ["/tmp/local_mcp.py"],
                "cwd": "/tmp",
                "env": {"FILES_ALLOWED_ROOTS": "{{inputs.root}}"},
            }
        ]
    }
    skill_runner = _FakeSkillRunner(
        {
            "mcp": [
                {
                    "name": "local-mcp",
                    "transport": "stdio",
                    "command": "/usr/bin/python3",
                    "args": ["/tmp/local_mcp.py"],
                    "cwd": "/tmp",
                    "env": {"FILES_ALLOWED_ROOTS": "{{inputs.root}}"},
                }
            ]
        }
    )
    use_case = RenderMcpConfigUseCase(store=_FakeStore(_build_run(skill_snapshot)), skill_runner=skill_runner)

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="create_file",
            step_type=StepType.MCP,
            step={"type": "mcp", "mcp": "local-mcp", "tool": "files_action", "args": {}},
            context=_build_run().context,
        )
    )

    assert result.status == RenderMcpConfigStatus.RENDERED
    assert result.error is None
    assert result.mcp_config == RenderedMcpConfig(
        name="local-mcp",
        transport="stdio",
        command="/usr/bin/python3",
        args=["/tmp/local_mcp.py"],
        cwd="/tmp",
        env={"FILES_ALLOWED_ROOTS": "/tmp/work"},
    )
    assert skill_runner.render_calls
    assert skill_runner.load_calls == []


def test_render_mcp_config_rejects_non_mcp_step() -> None:
    use_case = RenderMcpConfigUseCase(
        store=_FakeStore(_build_run()),
        skill_runner=_FakeSkillRunner({"mcp": []}),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="done",
            step_type=StepType.NOTIFY,
            step={"type": "notify", "message": "ok"},
            context=_build_run().context,
        )
    )

    assert result.status == RenderMcpConfigStatus.INVALID_CONFIG
    assert result.mcp_config is None
    assert result.error == "Step 'done' is not an mcp step"


def test_render_mcp_config_rejects_missing_declared_server() -> None:
    run = _build_run(
        {
            "mcp": [{"name": "other-mcp", "transport": "stdio", "command": "/bin/true"}]
        }
    )
    use_case = RenderMcpConfigUseCase(
        store=_FakeStore(run),
        skill_runner=_FakeSkillRunner(
            {"mcp": [{"name": "other-mcp", "transport": "stdio", "command": "/bin/true"}]}
        ),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="create_file",
            step_type=StepType.MCP,
            step={"type": "mcp", "mcp": "local-mcp", "tool": "files_action", "args": {}},
            context=_build_run().context,
        )
    )

    assert result.status == RenderMcpConfigStatus.INVALID_CONFIG
    assert result.mcp_config is None
    assert result.error == "MCP server 'local-mcp' not declared in skill 'local_mcp'"


def test_render_mcp_config_returns_rendered_http_config() -> None:
    run = _build_run(
        {
            "mcp": [
                {
                    "name": "chrome-mcp",
                    "transport": "streamable-http",
                    "url": "http://127.0.0.1:7821/mcp",
                }
            ]
        }
    )
    use_case = RenderMcpConfigUseCase(
        store=_FakeStore(run),
        skill_runner=_FakeSkillRunner(
            {
                "mcp": [
                    {
                        "name": "chrome-mcp",
                        "transport": "streamable-http",
                        "url": "http://127.0.0.1:7821/mcp",
                    }
                ]
            }
        ),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="open",
            step_type=StepType.MCP,
            step={"type": "mcp", "mcp": "chrome-mcp", "tool": "navigate_page", "args": {}},
            context=_build_run().context,
        )
    )

    assert result.status == RenderMcpConfigStatus.RENDERED
    assert result.mcp_config == RenderedMcpConfig(
        name="chrome-mcp",
        transport="streamable-http",
        url="http://127.0.0.1:7821/mcp",
    )


def test_render_mcp_config_renders_http_url_template() -> None:
    run = _build_run_with_inputs(
        host="127.0.0.1",
        port="8765",
        skill_snapshot={
            "mcp": [
                {
                    "name": "test-mcp",
                    "transport": "streamable-http",
                    "url": "http://{{inputs.host}}:{{inputs.port}}/mcp",
                }
            ]
        },
    )
    use_case = RenderMcpConfigUseCase(
        store=_FakeStore(run),
        skill_runner=_FakeSkillRunner(
            {
                "mcp": [
                    {
                        "name": "test-mcp",
                        "transport": "streamable-http",
                        "url": "http://{{inputs.host}}:{{inputs.port}}/mcp",
                    }
                ]
            }
        ),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="ping_server",
            step_type=StepType.MCP,
            step={"type": "mcp", "mcp": "test-mcp", "tool": "ping", "args": {}},
            context=run.context,
        )
    )

    assert result.status == RenderMcpConfigStatus.RENDERED
    assert result.mcp_config == RenderedMcpConfig(
        name="test-mcp",
        transport="streamable-http",
        url="http://127.0.0.1:8765/mcp",
    )


def test_render_mcp_config_requires_explicit_transport() -> None:
    run = _build_run(
        {
            "mcp": [
                {
                    "name": "local-mcp",
                    "command": "/usr/bin/python3",
                }
            ]
        }
    )
    use_case = RenderMcpConfigUseCase(
        store=_FakeStore(run),
        skill_runner=_FakeSkillRunner(
            {
                "mcp": [
                    {
                        "name": "local-mcp",
                        "command": "/usr/bin/python3",
                    }
                ]
            }
        ),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="create_file",
            step_type=StepType.MCP,
            step={"type": "mcp", "mcp": "local-mcp", "tool": "files_action", "args": {}},
            context=_build_run().context,
        )
    )

    assert result.status == RenderMcpConfigStatus.INVALID_CONFIG
    assert result.error == "MCP server 'local-mcp' requires explicit transport"


@pytest.mark.parametrize(
    ("raw_config", "expected_error"),
    [
        (
            {"name": "local-mcp", "transport": "stdio"},
            "MCP server 'local-mcp' requires command for stdio transport",
        ),
        (
            {"name": "test-mcp", "transport": "streamable-http"},
            "MCP server 'test-mcp' requires url for http transport",
        ),
        (
            {"name": "local-mcp", "transport": "stdio", "command": "/usr/bin/python3", "args": "bad"},
            "Invalid MCP args for server 'local-mcp'. Expected a list.",
        ),
        (
            {"name": "local-mcp", "transport": "stdio", "command": "/usr/bin/python3", "env": "bad"},
            "Invalid MCP env for server 'local-mcp'. Expected an object.",
        ),
        (
            {"name": "local-mcp", "transport": "websocket", "url": "ws://localhost:1234"},
            "Unsupported MCP transport 'websocket' for server 'local-mcp'",
        ),
    ],
)
def test_render_mcp_config_rejects_invalid_mcp_shapes(
    raw_config: dict[str, object],
    expected_error: str,
) -> None:
    server_name = str(raw_config["name"])
    run = _build_run({"mcp": [raw_config]})
    use_case = RenderMcpConfigUseCase(
        store=_FakeStore(run),
        skill_runner=_FakeSkillRunner({"mcp": [raw_config]}),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="bad_config",
            step_type=StepType.MCP,
            step={"type": "mcp", "mcp": server_name, "tool": "files_action", "args": {}},
            context=_build_run().context,
        )
    )

    assert result.status == RenderMcpConfigStatus.INVALID_CONFIG
    assert result.error == expected_error


def test_render_mcp_config_rejects_non_list_mcp_block() -> None:
    run = _build_run({"mcp": {"name": "local-mcp"}})  # type: ignore[arg-type]
    use_case = RenderMcpConfigUseCase(
        store=_FakeStore(run),
        skill_runner=_FakeSkillRunner({"mcp": {"name": "local-mcp"}}),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="create_file",
            step_type=StepType.MCP,
            step={"type": "mcp", "mcp": "local-mcp", "tool": "files_action", "args": {}},
            context=_build_run().context,
        )
    )

    assert result.status == RenderMcpConfigStatus.INVALID_CONFIG
    assert result.error == "Invalid MCP configuration for skill 'local_mcp'. Expected a list."


def test_render_mcp_config_rejects_unresolved_template() -> None:
    run = _build_run(
        {
            "mcp": [
                {
                    "name": "local-mcp",
                    "transport": "stdio",
                    "command": "{{inputs.python_bin}}",
                }
            ]
        }
    )
    use_case = RenderMcpConfigUseCase(
        store=_FakeStore(run),
        skill_runner=_FakeSkillRunner(
            {
                "mcp": [
                    {
                        "name": "local-mcp",
                        "transport": "stdio",
                        "command": "{{inputs.python_bin}}",
                    }
                ]
            }
        ),
    )

    result = use_case.execute(
        CurrentStep(
            run_id="run-1",
            step_index=0,
            step_id="create_file",
            step_type=StepType.MCP,
            step={"type": "mcp", "mcp": "local-mcp", "tool": "files_action", "args": {}},
            context=_build_run().context,
        )
    )

    assert result.status == RenderMcpConfigStatus.INVALID_CONFIG
    assert result.error == "Unresolved template in MCP config for server 'local-mcp' at 'mcp.command'"
