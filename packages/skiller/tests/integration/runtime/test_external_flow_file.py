from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from helpers.agent_config import FakeAgentConfigPort
from helpers.agent_runner import build_agent_runner

from skiller.application.action.action_mapper import ActionMapper
from skiller.application.action.action_uid_factory import ActionUidFactory
from skiller.application.agent.config.agent_step_mapper import AgentStepMapper
from skiller.application.agent.config.step_config_reader import AgentStepConfigReader
from skiller.application.agent.mapper.agent_step_execution_mapper import (
    AgentStepExecutionMapper,
)
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
from skiller.application.use_cases.ingress.handle_channel import HandleChannelUseCase
from skiller.application.use_cases.ingress.handle_input import (
    HandleInputInput,
    HandleInputUseCase,
)
from skiller.application.use_cases.ingress.handle_webhook import (
    HandleWebhookInput,
    HandleWebhookUseCase,
)
from skiller.application.use_cases.query.get_run import GetRunUseCase
from skiller.application.use_cases.query.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.render.render_current_step import (
    CurrentStepStatus,
    RenderCurrentStepUseCase,
)
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
from skiller.application.use_cases.run.resolve_cleanup import ResolveCleanupUseCase
from skiller.application.use_cases.run.resolve_end_action import ResolveEndActionUseCase
from skiller.application.use_cases.run.resolve_end_action_config import (
    ResolveEndActionConfigParser,
)
from skiller.application.use_cases.run.resume_run import ResumeRunUseCase
from skiller.application.use_cases.run.sync_snapshot import SyncSnapshotUseCase
from skiller.application.use_cases.webhook.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.webhook.remove_webhook import RemoveWebhookUseCase
from skiller.application.waits.service import WaitApplicationService
from skiller.domain.event.event_model import RunWaitingPayload, StepSuccessPayload
from skiller.infrastructure.agent.agent_context_store import AgentContextStore
from skiller.infrastructure.db.datasource.sqlite_agent_context_datasource import (
    SqliteAgentContextDatasource,
)
from skiller.infrastructure.db.datasource.sqlite_wait_datasource import SqliteWaitDatasource
from skiller.infrastructure.db.sqlite_agent_steering_store import SqliteAgentSteeringStore
from skiller.infrastructure.db.sqlite_external_event_store import SqliteExternalEventStore
from skiller.infrastructure.db.sqlite_run_store_port import SqliteRunStorePort
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_runtime_event_store import SqliteRuntimeEventStore
from skiller.infrastructure.db.sqlite_wait_store_port import SqliteWaitStorePort
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.flow.filesystem_flow_port import FilesystemFlowPort
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper
from skiller.infrastructure.llm.defaults.null_llm_port import NullLLMPort
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
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


def _event_store(store: SqliteRunStorePort) -> SqliteRuntimeEventStore:
    return SqliteRuntimeEventStore(store.db_path)


def _build_runtime(store: SqliteRunStorePort) -> RunApplicationService:
    runtime_event_store = SqliteRuntimeEventStore(store.db_path)
    external_event_store = SqliteExternalEventStore(store.db_path)
    wait_store = SqliteWaitStorePort(SqliteWaitDatasource(store.db_path))
    agent_context_store = AgentContextStore(
        SqliteAgentContextDatasource(store.db_path),
    )
    agent_steering_store = SqliteAgentSteeringStore(store.db_path)
    skill_runner = FilesystemSkillRunner(
        skills_dir="skills",
    )
    flow_port = FilesystemFlowPort(
        flows_dir=str(skill_runner.skills_dir),
        mapper=FlowYamlMapper(),
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
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, flow_runner=skill_runner)
    execute_agent_step_use_case = ExecuteAgentStepUseCase(
        store=store,
        runner=build_agent_runner(
            agent_context_store=agent_context_store,
            llm=NullLLMPort(),
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
        execution_mapper=AgentStepExecutionMapper(),
    )
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(
        store=store,
        mcp=mcp,
    )
    action_uid_factory = ActionUidFactory()
    execute_notify_step_use_case = ExecuteNotifyStepUseCase(
        store=store,
        action_mapper=ActionMapper(action_uid_factory),
    )
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
        wait_store=wait_store,
        external_event_store=external_event_store,
    )
    execute_wait_input_step_use_case = ExecuteWaitInputStepUseCase(
        run_store=store,
        wait_store=wait_store,
        external_event_store=external_event_store,
    )
    execute_wait_webhook_step_use_case = ExecuteWaitWebhookStepUseCase(
        run_store=store,
        wait_store=wait_store,
        external_event_store=external_event_store,
    )
    sync_snapshot_use_case = SyncSnapshotUseCase(
        store=store,
        runner=skill_runner,
        events=runtime_event_store,
    )
    resolve_end_action_use_case = ResolveEndActionUseCase(
        store=store,
        config_parser=ResolveEndActionConfigParser(skill_runner, action_uid_factory),
    )
    resolve_cleanup_use_case = ResolveCleanupUseCase(store)
    run_executor = RunExecutor(
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        append_runtime_event_use_case=append_runtime_event_use_case,
        sync_snapshot_use_case=sync_snapshot_use_case,
        resolve_end_action_use_case=resolve_end_action_use_case,
        resolve_cleanup_use_case=resolve_cleanup_use_case,
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
        flow_checker_use_case=FlowCheckerUseCase(flow_port=flow_port),
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


def _build_waits(store: SqliteRunStorePort) -> WaitApplicationService:
    runtime_event_store = SqliteRuntimeEventStore(store.db_path)
    external_event_store = SqliteExternalEventStore(store.db_path)
    wait_store = SqliteWaitStorePort(SqliteWaitDatasource(store.db_path))
    webhook_registry = SqliteWebhookRegistry(store.db_path)
    return WaitApplicationService(
        handle_input_use_case=HandleInputUseCase(
            run_store=store,
            external_event_store=external_event_store,
            runtime_event_store=runtime_event_store,
        ),
        handle_channel_use_case=HandleChannelUseCase(
            external_event_store=external_event_store,
            wait_store=wait_store,
        ),
        handle_webhook_use_case=HandleWebhookUseCase(
            external_event_store=external_event_store,
            wait_store=wait_store,
        ),
        list_webhooks_use_case=ListWebhooksUseCase(registry=webhook_registry),
        register_webhook_use_case=RegisterWebhookUseCase(registry=webhook_registry),
        remove_webhook_use_case=RemoveWebhookUseCase(registry=webhook_registry),
    )


def test_run_external_flow_file_succeeds() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_notify.yaml"
        skill_path.write_text(
            (
                "name: external_notify\n"
                "start: show_message\n"
                "inputs: {}\n"
                "steps:\n"
                "  - notify: show_message\n"
                "    message: external ok\n"
            ),
            encoding="utf-8",
        )

        store = SqliteRunStorePort(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(
            CreateRunInput(skill_ref=str(skill_path), inputs={}, skill_source="file")
        )

        run = store.get_run(run_result.run_id)
        assert run_result.status.value == "SUCCEEDED"
        assert run is not None
        assert run.source == "file"
        assert run.ref == str(skill_path)
        assert run.snapshot["name"] == "external_notify"
        events = _event_store(store).list_events(run_result.run_id)
        notify_event = _step_success_event(events, step_id="show_message")
        assert notify_event.payload.output["value"]["message"] == "external ok"


def test_external_notify_can_read_shell_output_value() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_shell_notify.yaml"
        skill_path.write_text(
            (
                "name: external_shell_notify\n"
                "start: inspect_cloudflared\n"
                "inputs: {}\n"
                "steps:\n"
                "  - shell: inspect_cloudflared\n"
                "    command: python3 -c \"print('x' * 400)\"\n"
                "    next: summarize_tunnels\n"
                "  - notify: summarize_tunnels\n"
                "    message: '{{output_value(\"inspect_cloudflared\").stdout}}'\n"
            ),
            encoding="utf-8",
        )

        store = SqliteRunStorePort(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(
            CreateRunInput(skill_ref=str(skill_path), inputs={}, skill_source="file")
        )

        run = store.get_run(run_result.run_id)
        assert run_result.status.value == "SUCCEEDED"
        assert run is not None
        notify_output = run.context.step_executions["summarize_tunnels"].output.to_public_dict()
        assert notify_output["value"]["message"] == ("x" * 400) + "\n"


def test_external_flow_file_is_snapshotted_at_run_creation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_notify.yaml"
        skill_path.write_text(
            (
                "name: external_notify\n"
                "start: show_message\n"
                "inputs: {}\n"
                "steps:\n"
                "  - notify: show_message\n"
                "    message: original\n"
            ),
            encoding="utf-8",
        )

        store = SqliteRunStorePort(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        skill_runner = FilesystemSkillRunner(skills_dir="skills")
        create_run_use_case = CreateRunUseCase(store, skill_runner)
        get_start_step_use_case = GetStartStepUseCase(store=store)
        render_current_step_use_case = RenderCurrentStepUseCase(
            store=store, skill_runner=skill_runner
        )

        run_id = create_run_use_case.execute(
            CreateRunInput(skill_ref=str(skill_path), inputs={}, skill_source="file")
        )
        get_start_step_use_case.execute(run_id)

        skill_path.write_text(
            (
                "name: external_notify\n"
                "start: show_message\n"
                "inputs: {}\n"
                "steps:\n"
                "  - notify: show_message\n"
                "    message: mutated\n"
            ),
            encoding="utf-8",
        )

        run = store.get_run(run_id)
        result = render_current_step_use_case.execute(run_id)

        assert run is not None
        assert run.snapshot["steps"][0]["message"] == "original"
        assert result.status == CurrentStepStatus.READY
        assert result.current_step is not None
        assert result.current_step.step["message"] == "original"


def test_external_wait_webhook_file_can_resume_manually() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait.yaml"
        skill_path.write_text(
            (
                "name: external_wait\n"
                "start: wait_merge\n"
                "inputs:\n"
                "  pr: string\n"
                "steps:\n"
                "  - wait_webhook: wait_merge\n"
                "    webhook: github-pr-merged\n"
                '    key: "{{inputs.pr}}"\n'
                "    next: done\n"
                "  - notify: done\n"
                "    message: resumed ok\n"
            ),
            encoding="utf-8",
        )

        store = SqliteRunStorePort(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(
            CreateRunInput(skill_ref=str(skill_path), inputs={"pr": "42"}, skill_source="file")
        )
        run_id = run_result.run_id
        run = store.get_run(run_id)

        assert run_result.status.value == "WAITING"
        assert run is not None
        assert run.status == "WAITING"

        wait_event = next(
            event for event in _event_store(store).list_events(run_id)
            if event.type == "RUN_WAITING")
        assert isinstance(wait_event.payload, RunWaitingPayload)
        assert wait_event.payload.output["value"]["webhook"] == "github-pr-merged"
        assert wait_event.payload.output["value"]["key"] == "42"

        resume_result = runtime.resume_run(run_id)
        resumed_run = store.get_run(run_id)

        assert resume_result.resume_status.value == "RESUMED"
        assert resume_result.status.value == "WAITING"
        assert resumed_run is not None
        assert resumed_run.status == "WAITING"

        events = _event_store(store).list_events(run_id)
        assert any(event.type == "RUN_RESUME" for event in events)
        assert not any(
            event.type == "STEP_SUCCESS" and event.step_type == "notify"
            for event in events
        )


def test_external_wait_webhook_file_can_resume_from_webhook() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait.yaml"
        skill_path.write_text(
            (
                "name: external_wait\n"
                "start: wait_merge\n"
                "inputs:\n"
                "  pr: string\n"
                "steps:\n"
                "  - wait_webhook: wait_merge\n"
                "    webhook: github-pr-merged\n"
                '    key: "{{inputs.pr}}"\n'
                "    next: done\n"
                "  - notify: done\n"
                "    message: resumed from webhook\n"
            ),
            encoding="utf-8",
        )

        store = SqliteRunStorePort(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(
            CreateRunInput(skill_ref=str(skill_path), inputs={"pr": "42"}, skill_source="file")
        )
        run_id = run_result.run_id

        assert run_result.status.value == "WAITING"

        waits = _build_waits(store)
        matched_runs = waits.handle_webhook(
            HandleWebhookInput(
                webhook="github-pr-merged",
                key="42",
                payload={"merged": True},
                dedup_key="dedup-1",
            )
        )
        matched_run = store.get_run(run_id)

        assert matched_runs.accepted is True
        assert matched_runs.duplicate is False
        assert matched_runs.run_ids == [run_id]
        assert matched_run is not None
        assert matched_run.status == "WAITING"

        resume_result = runtime.resume_run(run_id)
        resumed_run = store.get_run(run_id)

        assert resume_result.resume_status.value == "RESUMED"
        assert resume_result.status.value == "SUCCEEDED"
        assert resumed_run is not None
        assert resumed_run.status == "SUCCEEDED"

        events = _event_store(store).list_events(run_id)
        wait_resolved = _step_success_event(events, step_id="wait_merge")
        assert wait_resolved.payload.output == {
            "text": "Webhook received: github-pr-merged:42.",
            "value": {
                "webhook": "github-pr-merged",
                "key": "42",
                "payload": {"merged": True},
            },
            "body_ref": None,
        }
        notify_event = _step_success_event(events, step_id="done")
        assert notify_event.payload.output["value"]["message"] == "resumed from webhook"


def test_external_wait_input_file_can_resume_from_cli_input() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait_input.yaml"
        skill_path.write_text(
            (
                "name: external_wait_input\n"
                "start: ask_user\n"
                "inputs: {}\n"
                "steps:\n"
                "  - wait_input: ask_user\n"
                "    prompt: Write a short summary\n"
                "    next: done\n"
                "  - notify: done\n"
                "    message: '{{output_value(\"ask_user\").payload.text}}'\n"
            ),
            encoding="utf-8",
        )

        store = SqliteRunStorePort(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(
            CreateRunInput(skill_ref=str(skill_path), inputs={}, skill_source="file")
        )
        run_id = run_result.run_id

        assert run_result.status.value == "WAITING"

        waits = _build_waits(store)
        input_result = waits.handle_input(
            HandleInputInput(run_id=run_id, text="database timeout")
        )
        waiting_run = store.get_run(run_id)

        assert input_result.accepted is True
        assert input_result.run_ids == [run_id]
        assert waiting_run is not None
        assert waiting_run.status == "WAITING"

        resume_result = runtime.resume_run(run_id)
        resumed_run = store.get_run(run_id)

        assert resume_result.resume_status.value == "RESUMED"
        assert resume_result.status.value == "SUCCEEDED"
        assert resumed_run is not None
        assert resumed_run.status == "SUCCEEDED"
        assert (
            resumed_run.context.step_executions["ask_user"].input["prompt"]
            == "Write a short summary"
        )
        assert resumed_run.context.step_executions["ask_user"].output.to_public_dict()["value"] == {
            "prompt": "Write a short summary",
            "payload": {"text": "database timeout"},
        }
        assert resumed_run.context.step_executions["ask_user"].evaluation["input_event_id"]

        events = _event_store(store).list_events(run_id)
        run_waiting_event = next(event for event in events if event.type == "RUN_WAITING")
        assert run_waiting_event.step_id == "ask_user"
        assert run_waiting_event.step_type == "wait_input"
        assert isinstance(run_waiting_event.payload, RunWaitingPayload)
        assert run_waiting_event.payload.output["value"]["prompt"] == "Write a short summary"

        step_success_event = _step_success_event(events, step_id="ask_user")
        assert step_success_event.payload.output == {
            "text": "Input received.",
            "value": {
                "prompt": "Write a short summary",
                "payload": {"text": "database timeout"},
            },
            "body_ref": None,
        }

        notify_event = _step_success_event(events, step_id="done")
        assert notify_event.payload.output["value"]["message"] == "database timeout"


def test_external_wait_input_loop_does_not_reconsume_previous_input() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "external_wait_input_loop.yaml"
        skill_path.write_text(
            (
                "name: external_wait_input_loop\n"
                "start: ask_user\n"
                "inputs: {}\n"
                "steps:\n"
                "  - wait_input: ask_user\n"
                "    prompt: Write a short summary\n"
                "    next: echo\n"
                "  - notify: echo\n"
                "    message: '{{output_value(\"ask_user\").payload.text}}'\n"
                "    next: ask_user\n"
            ),
            encoding="utf-8",
        )

        store = SqliteRunStorePort(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(
            CreateRunInput(skill_ref=str(skill_path), inputs={}, skill_source="file")
        )
        run_id = run_result.run_id

        assert run_result.status.value == "WAITING"

        waits = _build_waits(store)
        first_input = waits.handle_input(HandleInputInput(run_id=run_id, text="first reply"))
        first_resume = runtime.resume_run(run_id)
        run_after_first_resume = store.get_run(run_id)

        assert first_input.accepted is True
        assert first_input.run_ids == [run_id]
        assert first_resume.resume_status.value == "RESUMED"
        assert first_resume.status.value == "WAITING"
        assert run_after_first_resume is not None
        assert run_after_first_resume.status == "WAITING"
        assert run_after_first_resume.current == "ask_user"
        assert run_after_first_resume.context.step_executions["ask_user"].output.to_public_dict()[
            "value"
        ]["payload"] == {"text": "first reply"}

        second_input = waits.handle_input(HandleInputInput(run_id=run_id, text="second reply"))
        second_resume = runtime.resume_run(run_id)
        run_after_second_resume = store.get_run(run_id)

        assert second_input.accepted is True
        assert second_input.run_ids == [run_id]
        assert second_resume.resume_status.value == "RESUMED"
        assert second_resume.status.value == "WAITING"
        assert run_after_second_resume is not None
        assert run_after_second_resume.status == "WAITING"
        assert run_after_second_resume.current == "ask_user"
        assert run_after_second_resume.context.step_executions["ask_user"].output.to_public_dict()[
            "value"
        ]["payload"] == {"text": "second reply"}

        events = _event_store(store).list_events(run_id)
        input_resolved_events = [
            event
            for event in events
            if event.type == "STEP_SUCCESS" and event.step_id == "ask_user"
        ]
        notify_events = [
            event
            for event in events
            if event.type == "STEP_SUCCESS" and event.step_id == "echo"
        ]
        input_waiting_events = [event for event in events if event.type == "RUN_WAITING"]

        assert len(input_resolved_events) == 2
        assert isinstance(input_resolved_events[0].payload, StepSuccessPayload)
        assert input_resolved_events[0].payload.output["value"]["payload"] == {
            "text": "first reply"
        }
        assert input_resolved_events[1].payload.output["value"]["payload"] == {
            "text": "second reply"
        }
        assert [event.payload.output["value"]["message"] for event in notify_events] == [
            "first reply",
            "second reply",
        ]
        assert len(input_waiting_events) == 3


def _step_success_event(events: list[object], *, step_id: str):
    return next(
        event
        for event in events
        if event.type == "STEP_SUCCESS" and event.step_id == step_id
    )
