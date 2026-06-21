import os
from dataclasses import dataclass
from pathlib import Path

from skiller.application.action.action_mapper import ActionMapper
from skiller.application.action.action_uid_factory import ActionUidFactory
from skiller.application.agent.agent_runner import AgentRunner
from skiller.application.agent.config.agent_step_mapper import AgentStepMapper
from skiller.application.agent.config.output_truncator import OutputTruncator
from skiller.application.agent.config.step_config_reader import AgentStepConfigReader
from skiller.application.agent.context.agent_context_manager import AgentContextManager
from skiller.application.agent.context.agent_context_publisher import (
    AgentContextPublisher,
)
from skiller.application.agent.event.agent_event_draft_builder import (
    AgentEventDraftBuilder,
)
from skiller.application.agent.event.agent_event_publisher import AgentEventPublisher
from skiller.application.agent.llmodel.llm_model_manager import LLMModelManager
from skiller.application.agent.mapper.agent_step_execution_mapper import (
    AgentStepExecutionMapper,
)
from skiller.application.agent.mapper.error_mapper import AgentErrorMapper
from skiller.application.agent.mapper.feedback import AgentRunnerFeedback
from skiller.application.agent.prompt.prompt_builder import AgentPromptBuilder
from skiller.application.agent.tools.agent_tool_executor import AgentToolExecutor
from skiller.application.agent.tools.tool_manager import ToolManager
from skiller.application.agents.mapper import AgentServiceMapper
from skiller.application.agents.service import AgentApplicationService
from skiller.application.query_mapper import RunStatusMapper
from skiller.application.query_service import RunQueryService
from skiller.application.runs.executor import RunExecutor
from skiller.application.runs.mapper import RunServiceMapper
from skiller.application.runs.service import RunApplicationService
from skiller.application.tools.files import FilesTool
from skiller.application.tools.notify import NotifyTool
from skiller.application.tools.shell import ShellProcessTool
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.use_cases.agent.get_agent_stats import GetAgentStatsUseCase
from skiller.application.use_cases.agent.interrupt_agent import InterruptAgentUseCase
from skiller.application.use_cases.agent.list_agent_models import ListAgentModelsUseCase
from skiller.application.use_cases.agent.select_agent_model import SelectAgentModelUseCase
from skiller.application.use_cases.execute.execute_agent_step import (
    ExecuteAgentStepUseCase,
)
from skiller.application.use_cases.execute.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute.execute_notify_step import (
    ExecuteNotifyStepUseCase,
)
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
from skiller.application.use_cases.flow.flow_readiness_checker import (
    FlowReadinessCheckerUseCase,
)
from skiller.application.use_cases.ingress.handle_channel import HandleChannelUseCase
from skiller.application.use_cases.ingress.handle_input import HandleInputUseCase
from skiller.application.use_cases.ingress.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.query.get_run import GetRunUseCase
from skiller.application.use_cases.query.get_run_logs import GetRunLogsUseCase
from skiller.application.use_cases.query.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.query.get_runs import GetRunsUseCase
from skiller.application.use_cases.query.get_waiting_metadata import (
    GetWaitingMetadataUseCase,
)
from skiller.application.use_cases.query.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.render.render_current_step import (
    RenderCurrentStepUseCase,
)
from skiller.application.use_cases.render.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.run.append_runtime_event import AppendRuntimeEventUseCase
from skiller.application.use_cases.run.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.run.complete_run import CompleteRunUseCase
from skiller.application.use_cases.run.create_run import CreateRunUseCase
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
from skiller.application.waits.channel_mapper import ChannelWaitMapper
from skiller.application.waits.input_mapper import InputWaitMapper
from skiller.application.waits.service import WaitApplicationService
from skiller.application.waits.webhook_mapper import WebhookWaitMapper
from skiller.di.llm_client_factory import LLMClientFactory
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.tool.tool_contract import ToolDefinition
from skiller.infrastructure.agent.agent_context_store import AgentContextStore
from skiller.infrastructure.config.agent_config_mapper import AgentConfigMapper
from skiller.infrastructure.config.json_agent_config import JsonAgentConfig
from skiller.infrastructure.config.settings import Settings, get_settings
from skiller.infrastructure.db.datasource.sqlite_agent_context_datasource import (
    SqliteAgentContextDatasource,
)
from skiller.infrastructure.db.datasource.sqlite_run_agent_datasource import (
    SqliteRunAgentDatasource,
)
from skiller.infrastructure.db.datasource.sqlite_wait_datasource import SqliteWaitDatasource
from skiller.infrastructure.db.sqlite_agent_steering_store import SqliteAgentSteeringStore
from skiller.infrastructure.db.sqlite_external_event_store import SqliteExternalEventStore
from skiller.infrastructure.db.sqlite_run_agent_store import SqliteRunAgentStore
from skiller.infrastructure.db.sqlite_run_query_store import SqliteRunQueryStore
from skiller.infrastructure.db.sqlite_run_store_port import SqliteRunStorePort
from skiller.infrastructure.db.sqlite_runtime_bootstrap import SqliteRuntimeBootstrap
from skiller.infrastructure.db.sqlite_runtime_event_store import SqliteRuntimeEventStore
from skiller.infrastructure.db.sqlite_wait_store_port import SqliteWaitStorePort
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.flow.filesystem_flow_port import FilesystemFlowPort
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.channels.default_channel_sender import DefaultChannelSender
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP
from skiller.infrastructure.tools.process.default_tool_process import DefaultToolProcessRunner
from skiller.infrastructure.tools.webhooks.default_server_status import DefaultServerStatus


@dataclass(frozen=True)
class RuntimeContainer:
    settings: Settings
    agent_service: AgentApplicationService
    agent_mapper: AgentServiceMapper
    run_service: RunApplicationService
    run_mapper: RunServiceMapper
    query_service: RunQueryService
    status_mapper: RunStatusMapper
    wait_service: WaitApplicationService
    input_wait_mapper: InputWaitMapper
    channel_wait_mapper: ChannelWaitMapper
    webhook_wait_mapper: WebhookWaitMapper


def build_runtime_container(
    settings: Settings | None = None,
    *,
    skills_dir: str | None = None,
) -> RuntimeContainer:
    cfg = settings or get_settings()
    runtime_bootstrap = SqliteRuntimeBootstrap(cfg.db_path)
    store = SqliteRunStorePort(cfg.db_path)
    wait_datasource = SqliteWaitDatasource(cfg.db_path)
    wait_store = SqliteWaitStorePort(wait_datasource)
    external_event_store = SqliteExternalEventStore(cfg.db_path)
    runtime_event_store = SqliteRuntimeEventStore(cfg.db_path)
    agent_context_datasource = SqliteAgentContextDatasource(cfg.db_path)
    agent_context_store = AgentContextStore(agent_context_datasource)
    run_agent_datasource = SqliteRunAgentDatasource(cfg.db_path)
    run_agent_store = SqliteRunAgentStore(run_agent_datasource)
    agent_steering_store = SqliteAgentSteeringStore(cfg.db_path)
    run_query = SqliteRunQueryStore(cfg.db_path)
    webhook_registry = SqliteWebhookRegistry(cfg.db_path)
    filesystem_skill_runner = FilesystemSkillRunner(
        skills_dir=skills_dir,
    )
    skill_runner: RunnerPort = filesystem_skill_runner
    flow_port = FilesystemFlowPort(
        flows_dir=str(filesystem_skill_runner.skills_dir),
        mapper=FlowYamlMapper(),
    )
    shell_tool = ShellProcessTool()
    notify_tool = NotifyTool()
    files_tool = FilesTool()
    agent_tools = (
        shell_tool,
        notify_tool,
        files_tool,
    )
    agent_config = JsonAgentConfig(
        config_path_global=Path.home() / ".skiller" / "settings" / "agent.json",
        config_mapper=AgentConfigMapper(
            env=os.environ,
            tools=agent_tools,
        ),
        env=os.environ,
    )
    llm_model = _build_llm_model_manager()
    mcp = DefaultMCP()
    shell_runtime_config = _build_shell_runtime_config()
    tool_process_runner = DefaultToolProcessRunner()
    server_status = DefaultServerStatus(cfg)
    channel_sender = DefaultChannelSender()
    tool_manager = _build_agent_tool_manager(agent_tools)
    action_uid_factory = ActionUidFactory()

    bootstrap_runtime_use_case = BootstrapRuntimeUseCase(
        store=runtime_bootstrap,
    )

    create_run_use_case = CreateRunUseCase(store, skill_runner)
    delete_run_use_case = DeleteRunUseCase(store)
    append_runtime_event_use_case = AppendRuntimeEventUseCase(runtime_event_store)
    complete_run_use_case = CompleteRunUseCase(store)
    fail_run_use_case = FailRunUseCase(store)
    get_start_step_use_case = GetStartStepUseCase(store=store)
    mark_notify_action_done_use_case = MarkNotifyActionDoneUseCase(
        store=store,
        events=runtime_event_store,
    )
    handle_input_use_case = HandleInputUseCase(
        run_store=store,
        external_event_store=external_event_store,
        runtime_event_store=runtime_event_store,
        steering=agent_steering_store,
    )
    handle_channel_use_case = HandleChannelUseCase(
        external_event_store=external_event_store,
        wait_store=wait_store,
    )
    handle_webhook_use_case = HandleWebhookUseCase(
        external_event_store=external_event_store,
        wait_store=wait_store,
    )
    list_webhooks_use_case = ListWebhooksUseCase(registry=webhook_registry)
    register_webhook_use_case = RegisterWebhookUseCase(registry=webhook_registry)
    remove_webhook_use_case = RemoveWebhookUseCase(registry=webhook_registry)
    interrupt_agent_use_case = InterruptAgentUseCase(
        store=store,
        steering=agent_steering_store,
    )
    flow_checker_use_case = FlowCheckerUseCase(flow_port=flow_port)
    flow_readiness_checker_use_case = FlowReadinessCheckerUseCase(
        runner=skill_runner,
        server_status=server_status,
        channel_sender=channel_sender,
    )

    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, flow_runner=skill_runner)
    agent_feedback = AgentRunnerFeedback()
    agent_context_publisher = AgentContextPublisher(
        agent_context_store,
        run_agent_store,
        agent_feedback,
    )
    agent_context_manager = AgentContextManager(
        agent_context_store=agent_context_store,
        run_agent_store=run_agent_store,
        prompt_builder=AgentPromptBuilder(),
    )
    get_agent_stats_use_case = GetAgentStatsUseCase(
        run_store=store,
        run_agent_store=run_agent_store,
        context_stats=agent_context_store,
        agent_config=agent_config,
        skill_runner=skill_runner,
    )
    list_agent_models_use_case = ListAgentModelsUseCase(
        run_store=store,
        agent_config=agent_config,
        skill_runner=skill_runner,
    )
    select_agent_model_use_case = SelectAgentModelUseCase(
        run_store=store,
        agent_config=agent_config,
        skill_runner=skill_runner,
    )
    agent_event_publisher = AgentEventPublisher(
        runtime_event_store,
        AgentEventDraftBuilder(),
        OutputTruncator(),
    )
    execute_agent_step_use_case = ExecuteAgentStepUseCase(
        store=store,
        runner=AgentRunner(
            agent_context_store=agent_context_store,
            llm_model=llm_model,
            context_manager=agent_context_manager,
            error_mapper=AgentErrorMapper(),
            feedback=agent_feedback,
            context_publisher=agent_context_publisher,
            event_publisher=agent_event_publisher,
            tool_execution=AgentToolExecutor(
                context_publisher=agent_context_publisher,
                event_publisher=agent_event_publisher,
                steering=agent_steering_store,
                tool_manager=tool_manager,
                process_runner=tool_process_runner,
                feedback=agent_feedback,
            ),
        ),
        step_mapper=AgentStepMapper(),
        config_reader=AgentStepConfigReader(
            agent_config=agent_config,
            run_store=store,
            skill_runner=skill_runner,
            tool_manager=tool_manager,
        ),
        execution_mapper=AgentStepExecutionMapper(),
    )
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(
        store=store,
        mcp=mcp,
    )
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
        shell_config=shell_runtime_config,
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
    resume_run_use_case = ResumeRunUseCase(store=store)
    get_waiting_metadata_use_case = GetWaitingMetadataUseCase(
        store=store,
        skill_runner=skill_runner,
    )
    get_run_use_case = GetRunUseCase(store)
    get_run_status_use_case = GetRunStatusUseCase(store)
    get_run_logs_use_case = GetRunLogsUseCase(runtime_event_store)
    get_runs_use_case = GetRunsUseCase(run_query)
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
    query_service = RunQueryService(
        get_run_status_use_case=get_run_status_use_case,
        get_run_logs_use_case=get_run_logs_use_case,
        get_runs_use_case=get_runs_use_case,
        get_waiting_metadata_use_case=get_waiting_metadata_use_case,
    )
    wait_service = WaitApplicationService(
        handle_input_use_case=handle_input_use_case,
        handle_channel_use_case=handle_channel_use_case,
        handle_webhook_use_case=handle_webhook_use_case,
        list_webhooks_use_case=list_webhooks_use_case,
        register_webhook_use_case=register_webhook_use_case,
        remove_webhook_use_case=remove_webhook_use_case,
    )
    run_service = RunApplicationService(
        bootstrap_runtime_use_case=bootstrap_runtime_use_case,
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=create_run_use_case,
        delete_run_use_case=delete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        get_start_step_use_case=get_start_step_use_case,
        flow_checker_use_case=flow_checker_use_case,
        flow_readiness_checker_use_case=flow_readiness_checker_use_case,
        resume_run_use_case=resume_run_use_case,
        mark_notify_action_done_use_case=mark_notify_action_done_use_case,
        get_run_use_case=get_run_use_case,
        run_executor=run_executor,
    )
    run_mapper = RunServiceMapper()
    status_mapper = RunStatusMapper()
    input_wait_mapper = InputWaitMapper()
    channel_wait_mapper = ChannelWaitMapper()
    webhook_wait_mapper = WebhookWaitMapper()

    agent_service = AgentApplicationService(
        interrupt_agent_use_case=interrupt_agent_use_case,
        get_agent_stats_use_case=get_agent_stats_use_case,
        list_agent_models_use_case=list_agent_models_use_case,
        select_agent_model_use_case=select_agent_model_use_case,
    )
    agent_mapper = AgentServiceMapper()
    return RuntimeContainer(
        settings=cfg,
        agent_service=agent_service,
        agent_mapper=agent_mapper,
        run_service=run_service,
        run_mapper=run_mapper,
        query_service=query_service,
        status_mapper=status_mapper,
        wait_service=wait_service,
        input_wait_mapper=input_wait_mapper,
        channel_wait_mapper=channel_wait_mapper,
        webhook_wait_mapper=webhook_wait_mapper,
    )


def _build_llm_model_manager() -> LLMModelManager:
    return LLMModelManager(client_resolver=LLMClientFactory())


def _build_agent_tool_manager(tools: tuple[ToolDefinition, ...]) -> ToolManager:
    return ToolManager(
        tools=list(tools),
    )


def _build_shell_runtime_config() -> ShellToolRuntimeConfig:
    return ShellToolRuntimeConfig(
        definition=ShellProcessTool,
        allowed_paths=(),
        allowlist_enabled=False,
        allow_env_prefix=True,
        allowed_commands=(),
    )
