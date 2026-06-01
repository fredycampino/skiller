from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from helpers.agent_config import FakeAgentConfigPort
from helpers.agent_runner import build_agent_runner

from skiller.application.agent.config.agent_step_mapper import AgentStepMapper
from skiller.application.agent.config.step_config_reader import AgentStepConfigReader
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.application.runs.executor import RunExecutor
from skiller.application.runs.service import RunApplicationService
from skiller.application.tools.shell import ShellProcessTool
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.use_cases.execute.execute_agent_step import (
    ExecuteAgentStepUseCase,
)
from skiller.application.use_cases.execute.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute.execute_send_step import ExecuteSendStepUseCase
from skiller.application.use_cases.execute.execute_shell_step import ExecuteShellStepUseCase
from skiller.application.use_cases.execute.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute.execute_wait_channel_step import (
    ExecuteWaitChannelStepUseCase,
)
from skiller.application.use_cases.execute.execute_wait_input_step import (
    ExecuteWaitInputStepUseCase,
)
from skiller.application.use_cases.execute.execute_wait_webhook_step import (
    ExecuteWaitWebhookStepUseCase,
)
from skiller.application.use_cases.execute.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.flow.flow_checker import FlowCheckerUseCase
from skiller.application.use_cases.flow.flow_readiness_checker import FlowReadinessCheckerUseCase
from skiller.application.use_cases.query.get_run import GetRunUseCase
from skiller.application.use_cases.render.render_current_step import RenderCurrentStepUseCase
from skiller.application.use_cases.render.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase
from skiller.application.use_cases.run.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.run.complete_run import CompleteRunUseCase
from skiller.application.use_cases.run.create_run import CreateRunInput, CreateRunUseCase
from skiller.application.use_cases.run.delete_run import DeleteRunUseCase
from skiller.application.use_cases.run.fail_run import FailRunUseCase
from skiller.application.use_cases.run.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.run.mark_notify_action_done import (
    MarkNotifyActionDoneUseCase,
)
from skiller.application.use_cases.run.resume_run import ResumeRunUseCase
from skiller.application.use_cases.run.sync_snapshot import SyncSnapshotUseCase
from skiller.infrastructure.agent.agent_context_store import AgentContextStore
from skiller.infrastructure.db.sqlite_agent_context_datasource import (
    SqliteAgentContextDatasource,
)
from skiller.infrastructure.db.sqlite_agent_steering_store import SqliteAgentSteeringStore
from skiller.infrastructure.db.sqlite_external_event_store import SqliteExternalEventStore
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_runtime_event_store import SqliteRuntimeEventStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.client import MCPClientTool
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP
from skiller.infrastructure.tools.process.default_tool_process import DefaultToolProcessRunner

pytestmark = [
    pytest.mark.integration,
]


class _FakeServerStatus:
    def is_available(self) -> bool:
        return True


class _FakeChannelSender:
    def is_available(self, *, channel: str) -> bool:
        _ = channel
        return True

    def send_text(self, *, channel: str, key: str, message: str) -> SimpleNamespace:
        return SimpleNamespace(
            channel=channel,
            key=key,
            message=message,
            message_id="message-1",
        )


def _event_store(store: SqliteStateStore) -> SqliteRuntimeEventStore:
    return SqliteRuntimeEventStore(store.db_path)


@pytest.fixture(autouse=True)
def stub_runtime_mcp_calls() -> None:
    """Override the runtime integration autouse fixture for this module."""
    return None


@pytest.fixture(autouse=True)
def require_real_mcp_runtime() -> None:
    if os.getenv("RUN_REAL_MCP_TESTS") != "1":
        pytest.skip("Set RUN_REAL_MCP_TESTS=1 to run real MCP integration tests")


def _build_runtime(store: SqliteStateStore) -> RunApplicationService:
    runtime_event_store = SqliteRuntimeEventStore(store.db_path)
    external_event_store = SqliteExternalEventStore(store.db_path)
    agent_context_store = AgentContextStore(
        SqliteAgentContextDatasource(store.db_path),
    )
    agent_steering_store = SqliteAgentSteeringStore(store.db_path)
    skill_runner = FilesystemSkillRunner(
        skills_dir="skills",
    )
    mcp = DefaultMCP()
    shell_tool = ShellProcessTool()
    agent_tool_manager = ToolManager(tools=[])
    tool_process_runner = DefaultToolProcessRunner()
    channel_sender = _FakeChannelSender()
    fail_run_use_case = FailRunUseCase(store)
    append_runtime_event_use_case = AppendRuntimeEventUseCase(runtime_event_store)
    complete_run_use_case = CompleteRunUseCase(store)
    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_agent_step_use_case = ExecuteAgentStepUseCase(
        store=store,
        runner=build_agent_runner(
            agent_context_store=agent_context_store,
            llm=NullLLM(),
            tool_manager=agent_tool_manager,
            append_runtime_event_use_case=append_runtime_event_use_case,
        ),
        step_mapper=AgentStepMapper(),
        config_reader=AgentStepConfigReader(
            agent_config=FakeAgentConfigPort(),
            run_store=store,
            skill_runner=skill_runner,
            tool_manager=agent_tool_manager,
        ),
    )
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(
        store=store,
        mcp=mcp,
    )
    execute_notify_step_use_case = ExecuteNotifyStepUseCase(store=store)
    execute_send_step_use_case = ExecuteSendStepUseCase(
        store=store,
        channel_sender=channel_sender,
    )
    execute_shell_step_use_case = ExecuteShellStepUseCase(
        store=store,
        shell_tool=shell_tool,
        shell_config=ShellToolRuntimeConfig(
            definition=ShellProcessTool,
            allowed_paths=(),
            allowlist_enabled=False,
            allow_env_prefix=True,
            allowed_commands=(),
        ),
        process_runner=tool_process_runner,
        agent_steering_store=agent_steering_store,
    )
    execute_switch_step_use_case = ExecuteSwitchStepUseCase(store=store)
    execute_when_step_use_case = ExecuteWhenStepUseCase(store=store)
    execute_wait_channel_step_use_case = ExecuteWaitChannelStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=external_event_store,
    )
    execute_wait_input_step_use_case = ExecuteWaitInputStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=external_event_store,
    )
    execute_wait_webhook_step_use_case = ExecuteWaitWebhookStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=external_event_store,
    )
    sync_snapshot_use_case = SyncSnapshotUseCase(
        store=store,
        runner=skill_runner,
        events=runtime_event_store,
    )
    run_executor = RunExecutor(
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        append_runtime_event_use_case=append_runtime_event_use_case,
        sync_snapshot_use_case=sync_snapshot_use_case,
        render_current_step_use_case=render_current_step_use_case,
        render_mcp_config_use_case=render_mcp_config_use_case,
        execute_agent_step_use_case=execute_agent_step_use_case,
        execute_assign_step_use_case=execute_assign_step_use_case,
        execute_mcp_step_use_case=execute_mcp_step_use_case,
        execute_notify_step_use_case=execute_notify_step_use_case,
        execute_send_step_use_case=execute_send_step_use_case,
        execute_shell_step_use_case=execute_shell_step_use_case,
        execute_switch_step_use_case=execute_switch_step_use_case,
        execute_when_step_use_case=execute_when_step_use_case,
        execute_wait_channel_step_use_case=execute_wait_channel_step_use_case,
        execute_wait_input_step_use_case=execute_wait_input_step_use_case,
        execute_wait_webhook_step_use_case=execute_wait_webhook_step_use_case,
    )

    runtime = RunApplicationService(
        bootstrap_runtime_use_case=BootstrapRuntimeUseCase(
            store=SqliteRuntimeBootstrap(store.db_path),
        ),
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=CreateRunUseCase(store, skill_runner),
        delete_run_use_case=DeleteRunUseCase(store),
        fail_run_use_case=fail_run_use_case,
        get_start_step_use_case=GetStartStepUseCase(store=store),
        flow_checker_use_case=FlowCheckerUseCase(runner=skill_runner),
        flow_readiness_checker_use_case=FlowReadinessCheckerUseCase(
            runner=skill_runner,
            server_status=_FakeServerStatus(),
            channel_sender=channel_sender,
        ),
        resume_run_use_case=ResumeRunUseCase(store=store),
        mark_notify_action_done_use_case=MarkNotifyActionDoneUseCase(
            store=store,
            events=runtime_event_store,
        ),
        get_run_use_case=GetRunUseCase(store),
        run_executor=run_executor,
    )
    return runtime


def _pick_free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    except PermissionError:
        pytest.skip("Local TCP sockets are not available in this environment")


def _wait_until_http_endpoint_ready(endpoint: str, timeout_seconds: float = 8.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if MCPClientTool()._is_endpoint_ready(endpoint):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for MCP endpoint {endpoint}")


@pytest.fixture
def http_mcp_server() -> str:
    port = _pick_free_port()
    endpoint = f"http://127.0.0.1:{port}/mcp"
    server_script = Path(
        "packages/skiller/tests/integration/runtime/fixtures/mcp/test_mcp_server.py"
    )
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, str(server_script)],
        cwd=str(Path.cwd()),
        env={
            **os.environ,
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": str(port),
            "MCP_PATH": "/mcp",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_http_endpoint_ready(endpoint)
        yield endpoint
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_stdio_mcp_test_with_real_fixture() -> None:
    file_path = Path("/tmp") / f"skiller-e2e-{uuid.uuid4().hex}.txt"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = SqliteStateStore(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()

        runtime = _build_runtime(store)
        run_result = runtime.run(
            CreateRunInput(
                skill_ref="stdio_mcp_test",
                inputs={"file_path": str(file_path), "content": "hola-e2e"},
            )
        )

        run = store.get_run(run_result.run_id)
        assert run_result.status.value == "SUCCEEDED"
        assert run is not None
        assert run.status == "SUCCEEDED"
        assert file_path.read_text(encoding="utf-8") == "hola-e2e"
        events = _event_store(store).list_events(run_result.run_id)
        mcp_event = next(
            event
            for event in events
            if event.type == "STEP_SUCCESS" and event.payload["step_type"] == "mcp"
        )
        assert mcp_event.payload["output"]["value"]["data"]["ok"] is True
        assert mcp_event.payload["output"]["value"]["data"]["tool"] == "files_action"


def test_http_mcp_test_with_real_fixture(http_mcp_server: str) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = SqliteStateStore(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()

        runtime = _build_runtime(store)
        run_result = runtime.run(
            CreateRunInput(
                skill_ref="http_mcp_test",
                inputs={"mcp_url": http_mcp_server},
            )
        )

        run = store.get_run(run_result.run_id)
        assert run_result.status.value == "SUCCEEDED"
        assert run is not None
        assert run.status == "SUCCEEDED"
        events = _event_store(store).list_events(run_result.run_id)
        mcp_event = next(
            event
            for event in events
            if event.type == "STEP_SUCCESS" and event.payload["step_type"] == "mcp"
        )
        assert mcp_event.payload["output"]["value"]["data"]["ok"] is True
        assert mcp_event.payload["output"]["value"]["data"]["tool"] == "ping"
