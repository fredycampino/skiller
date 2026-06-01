import tempfile
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
from skiller.domain.event.event_model import StepSuccessPayload
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
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP
from skiller.infrastructure.tools.process.default_tool_process import DefaultToolProcessRunner

pytestmark = pytest.mark.integration


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


@pytest.mark.parametrize(("skill_ref", "inputs"), [("notify_test", {})])
def test_basic_skill_examples_succeed(
    skill_ref: str,
    inputs: dict[str, str],
) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store = SqliteStateStore(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()

        runtime = _build_runtime(store)
        run_result = runtime.run(CreateRunInput(skill_ref=skill_ref, inputs=inputs))

        run_id = run_result.run_id
        run = store.get_run(run_id)
        assert run is not None
        assert run_result.status.value == "SUCCEEDED"
        assert run.status == "SUCCEEDED"

        events = _event_store(store).list_events(run_id)
        assert any(event.type == "RUN_FINISHED" for event in events)
        assert any(event.type == "STEP_STARTED" for event in events)
        assert any(event.type == "STEP_SUCCESS" for event in events)

        main_event = _step_success_event(events, step_id="show_message")
        assert main_event.step_type == "notify"
        assert main_event.payload == StepSuccessPayload(
            output={
                "text": "notify smoke ok",
                "value": {"message": "notify smoke ok", "format": "simple"},
                "body_ref": None,
            },
        )


def test_assign_step_succeeds_from_external_skill_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "assign.yaml"
        skill_path.write_text(
            (
                "name: assign_demo\n"
                "start: prepare_action\n"
                "inputs:\n"
                "  issue: string\n"
                "steps:\n"
                "  - assign: prepare_action\n"
                "    values:\n"
                "      action: retry\n"
                "      summary: '{{inputs.issue}}'\n"
                "      meta:\n"
                "        source: assign\n"
                "    next: done\n"
                "  - notify: done\n"
                "    message: '{{output_value(\"prepare_action\").assigned.action}}'\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(
            CreateRunInput(
                skill_ref=str(skill_path),
                inputs={"issue": "dependency timeout"},
                skill_source="file",
            )
        )

        run = store.get_run(run_result.run_id)
        assert run is not None
        assert run_result.status.value == "SUCCEEDED"
        assert run.context.step_executions["prepare_action"].output.to_public_dict() == {
            "text": "Values assigned.",
            "value": {
                "assigned": {
                    "action": "retry",
                    "summary": "dependency timeout",
                    "meta": {"source": "assign"},
                }
            },
            "body_ref": None,
        }

        events = _event_store(store).list_events(run_result.run_id)
        assign_event = _step_success_event(events, step_id="prepare_action")
        notify_event = _step_success_event(events, step_id="done")

        assert assign_event.step_type == "assign"
        assert assign_event.payload == StepSuccessPayload(
            output={
                "text": "Values assigned.",
                "value": {
                    "assigned": {
                        "action": "retry",
                        "summary": "dependency timeout",
                        "meta": {"source": "assign"},
                }
            },
            "body_ref": None,
            },
            next="done",
        )
        assert notify_event.payload.output["value"]["message"] == "retry"


def test_switch_step_routes_to_matching_branch_from_external_skill_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "switch.yaml"
        skill_path.write_text(
            (
                "name: switch_demo\n"
                "start: prepare_action\n"
                "steps:\n"
                "  - assign: prepare_action\n"
                "    values:\n"
                "      action: retry\n"
                "    next: decide_action\n"
                "  - switch: decide_action\n"
                "    value: '{{output_value(\"prepare_action\").assigned.action}}'\n"
                "    cases:\n"
                "      retry: retry_notice\n"
                "      ask_human: human_notice\n"
                "    default: unknown_action\n"
                "  - notify: retry_notice\n"
                "    message: retry chosen\n"
                "  - notify: human_notice\n"
                "    message: human chosen\n"
                "  - notify: unknown_action\n"
                "    message: unknown chosen\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(
            CreateRunInput(skill_ref=str(skill_path), inputs={}, skill_source="file")
        )

        run = store.get_run(run_result.run_id)
        assert run is not None
        assert run_result.status.value == "SUCCEEDED"
        assert run.context.step_executions["decide_action"].output.to_public_dict() == {
            "text": "Route selected: retry_notice.",
            "value": {"next_step_id": "retry_notice"},
            "body_ref": None,
        }

        events = _event_store(store).list_events(run_result.run_id)
        switch_event = _step_success_event(events, step_id="decide_action")
        notify_event = _step_success_event(events, step_id="retry_notice")

        assert switch_event.step_type == "switch"
        assert switch_event.payload == StepSuccessPayload(
            output={
                "text": "Route selected: retry_notice.",
                "value": {"next_step_id": "retry_notice"},
                "body_ref": None,
            },
            next="retry_notice",
        )
        assert notify_event.payload.output["value"]["message"] == "retry chosen"


def test_when_step_routes_to_first_matching_branch_from_external_skill_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        skill_path = Path(tmpdir) / "when.yaml"
        skill_path.write_text(
            (
                "name: when_demo\n"
                "start: prepare_score\n"
                "steps:\n"
                "  - assign: prepare_score\n"
                "    values:\n"
                "      score: 85\n"
                "    next: decide_score\n"
                "  - when: decide_score\n"
                "    value: '{{output_value(\"prepare_score\").assigned.score}}'\n"
                "    branches:\n"
                "      - gt: 90\n"
                "        then: excellent\n"
                "      - gt: 70\n"
                "        then: good\n"
                "    default: fail\n"
                "  - notify: excellent\n"
                "    message: excellent chosen\n"
                "  - notify: good\n"
                "    message: good chosen\n"
                "  - notify: fail\n"
                "    message: fail chosen\n"
            ),
            encoding="utf-8",
        )

        store = SqliteStateStore(db_path)
        SqliteRuntimeBootstrap(store.db_path).init_db()
        runtime = _build_runtime(store)

        run_result = runtime.run(
            CreateRunInput(skill_ref=str(skill_path), inputs={}, skill_source="file")
        )

        run = store.get_run(run_result.run_id)
        assert run is not None
        assert run_result.status.value == "SUCCEEDED"
        assert run.context.step_executions["decide_score"].output.to_public_dict() == {
            "text": "Route selected: good.",
            "value": {"next_step_id": "good"},
            "body_ref": None,
        }

        events = _event_store(store).list_events(run_result.run_id)
        when_event = _step_success_event(events, step_id="decide_score")
        notify_event = _step_success_event(events, step_id="good")

        assert when_event.step_type == "when"
        assert when_event.payload == StepSuccessPayload(
            output={
                "text": "Route selected: good.",
                "value": {"next_step_id": "good"},
                "body_ref": None,
            },
            next="good",
        )
        assert notify_event.payload.output["value"]["message"] == "good chosen"


def _step_success_event(events: list[object], *, step_id: str):
    return next(
        event
        for event in events
        if event.type == "STEP_SUCCESS" and event.step_id == step_id
    )
