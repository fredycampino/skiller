from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from skiller.application.run_worker_service import RunWorkerService
from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.application.use_cases.agent.execute_agent_step import ExecuteAgentStepUseCase
from skiller.application.use_cases.execute.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute.execute_llm_prompt_step import (
    ExecuteLlmPromptStepUseCase,
)
from skiller.application.use_cases.execute.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute.execute_shell_step import ExecuteShellStepUseCase
from skiller.application.use_cases.execute.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute.execute_wait_webhook_step import (
    ExecuteWaitWebhookStepUseCase,
)
from skiller.application.use_cases.execute.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.ingress.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.query.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.query.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.render.render_current_step import RenderCurrentStepUseCase
from skiller.application.use_cases.render.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase
from skiller.application.use_cases.run.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.run.complete_run import CompleteRunUseCase
from skiller.application.use_cases.run.create_run import CreateRunUseCase
from skiller.application.use_cases.run.delete_run import DeleteRunUseCase
from skiller.application.use_cases.run.fail_run import FailRunUseCase
from skiller.application.use_cases.run.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.run.resume_run import ResumeRunUseCase
from skiller.application.use_cases.skill.skill_checker import SkillCheckerUseCase
from skiller.application.use_cases.skill.skill_server_checker import SkillServerCheckerUseCase
from skiller.application.use_cases.webhook.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.webhook.remove_webhook import RemoveWebhookUseCase
from skiller.domain.large_result_truncator import LargeResultTruncator
from skiller.infrastructure.db.sqlite_agent_context_store import SqliteAgentContextStore
from skiller.infrastructure.db.sqlite_execution_output_store import SqliteExecutionOutputStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.client import MCPClientTool
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP
from skiller.infrastructure.tools.shell.default_shell import DefaultShellRunner

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


@pytest.fixture(autouse=True)
def stub_runtime_mcp_calls() -> None:
    """Override tests/integration/runtime/conftest.py autouse fixture for this module."""
    return None


@pytest.fixture(autouse=True)
def require_real_mcp_runtime() -> None:
    if os.getenv("RUN_REAL_MCP_TESTS") != "1":
        pytest.skip("Set RUN_REAL_MCP_TESTS=1 to run real MCP integration tests")


def _build_runtime(store: SqliteStateStore) -> RuntimeApplicationService:
    execution_output_store = SqliteExecutionOutputStore(store.db_path)
    execution_output_store.init_db()
    agent_context_store = SqliteAgentContextStore(store.db_path)
    skill_runner = FilesystemSkillRunner(
        skills_dir="skills",
        execution_output_store=execution_output_store,
    )
    webhook_registry = SqliteWebhookRegistry(store.db_path)
    mcp = DefaultMCP()
    shell = DefaultShellRunner()
    fail_run_use_case = FailRunUseCase(store)
    append_runtime_event_use_case = AppendRuntimeEventUseCase(store)
    complete_run_use_case = CompleteRunUseCase(store)
    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_agent_step_use_case = ExecuteAgentStepUseCase(
        store=store,
        agent_context_store=agent_context_store,
        llm=NullLLM(),
    )
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_llm_prompt_step_use_case = ExecuteLlmPromptStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        llm=NullLLM(),
        large_result_truncator=LargeResultTruncator(),
    )
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        mcp=mcp,
        large_result_truncator=LargeResultTruncator(),
    )
    execute_notify_step_use_case = ExecuteNotifyStepUseCase(store=store)
    execute_shell_step_use_case = ExecuteShellStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        shell=shell,
        large_result_truncator=LargeResultTruncator(),
    )
    execute_switch_step_use_case = ExecuteSwitchStepUseCase(store=store)
    execute_when_step_use_case = ExecuteWhenStepUseCase(store=store)
    execute_wait_webhook_step_use_case = ExecuteWaitWebhookStepUseCase(
        run_store=store,
        wait_store=store,
        external_event_store=store,
    )
    run_worker_service = RunWorkerService(
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        append_runtime_event_use_case=append_runtime_event_use_case,
        render_current_step_use_case=render_current_step_use_case,
        render_mcp_config_use_case=render_mcp_config_use_case,
        execute_agent_step_use_case=execute_agent_step_use_case,
        execute_assign_step_use_case=execute_assign_step_use_case,
        execute_llm_prompt_step_use_case=execute_llm_prompt_step_use_case,
        execute_mcp_step_use_case=execute_mcp_step_use_case,
        execute_notify_step_use_case=execute_notify_step_use_case,
        execute_shell_step_use_case=execute_shell_step_use_case,
        execute_switch_step_use_case=execute_switch_step_use_case,
        execute_when_step_use_case=execute_when_step_use_case,
        execute_wait_webhook_step_use_case=execute_wait_webhook_step_use_case,
    )

    runtime = RuntimeApplicationService(
        bootstrap_runtime_use_case=BootstrapRuntimeUseCase(
            store=store,
            execution_output_store=execution_output_store,
            webhook_registry=webhook_registry,
        ),
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=CreateRunUseCase(store, skill_runner),
        delete_run_use_case=DeleteRunUseCase(store),
        fail_run_use_case=fail_run_use_case,
        get_start_step_use_case=GetStartStepUseCase(store=store),
        skill_checker_use_case=SkillCheckerUseCase(skill_runner=skill_runner),
        skill_server_checker_use_case=SkillServerCheckerUseCase(
            skill_runner=skill_runner,
            server_status=_FakeServerStatus(),
            channel_sender=_FakeChannelSender(),
        ),
        handle_webhook_use_case=HandleWebhookUseCase(
            external_event_store=store,
            wait_store=store,
        ),
        list_webhooks_use_case=ListWebhooksUseCase(registry=webhook_registry),
        register_webhook_use_case=RegisterWebhookUseCase(registry=webhook_registry),
        remove_webhook_use_case=RemoveWebhookUseCase(registry=webhook_registry),
        resume_run_use_case=ResumeRunUseCase(store=store),
        get_run_status_use_case=GetRunStatusUseCase(store),
        run_worker_service=run_worker_service,
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
    server_script = Path("tests/integration/runtime/fixtures/mcp/test_mcp_server.py")
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
        store.init_db()

        runtime = _build_runtime(store)
        run_result = runtime.run(
            "stdio_mcp_test",
            {"file_path": str(file_path), "content": "hola-e2e"},
        )

        run = store.get_run(run_result["run_id"])
        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.status == "SUCCEEDED"
        assert file_path.read_text(encoding="utf-8") == "hola-e2e"
        events = store.list_events(run_result["run_id"])
        mcp_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step_type"] == "mcp"
        )
        assert mcp_event["payload"]["output"]["value"]["data"]["ok"] is True
        assert mcp_event["payload"]["output"]["value"]["data"]["tool"] == "files_action"


def test_http_mcp_test_with_real_fixture(http_mcp_server: str) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = SqliteStateStore(db_path)
        store.init_db()

        runtime = _build_runtime(store)
        run_result = runtime.run(
            "http_mcp_test",
            {"mcp_url": http_mcp_server},
        )

        run = store.get_run(run_result["run_id"])
        assert run_result["status"] == "SUCCEEDED"
        assert run is not None
        assert run.status == "SUCCEEDED"
        events = store.list_events(run_result["run_id"])
        mcp_event = next(
            event
            for event in events
            if event["type"] == "STEP_SUCCESS" and event["payload"]["step_type"] == "mcp"
        )
        assert mcp_event["payload"]["output"]["value"]["data"]["ok"] is True
        assert mcp_event["payload"]["output"]["value"]["data"]["tool"] == "ping"
