from dataclasses import dataclass

from skiller.application.query_service import RunQueryService
from skiller.application.run_worker_service import RunWorkerService
from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.application.use_cases.append_runtime_event import AppendRuntimeEventUseCase
from skiller.application.use_cases.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.complete_run import CompleteRunUseCase
from skiller.application.use_cases.create_run import CreateRunUseCase
from skiller.application.use_cases.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute_llm_prompt_step import ExecuteLlmPromptStepUseCase
from skiller.application.use_cases.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute_shell_step import ExecuteShellStepUseCase
from skiller.application.use_cases.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute_wait_input_step import ExecuteWaitInputStepUseCase
from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.get_execution_output import GetExecutionOutputUseCase
from skiller.application.use_cases.get_run_logs import GetRunLogsUseCase
from skiller.application.use_cases.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.get_runs import GetRunsUseCase
from skiller.application.use_cases.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.get_waiting_metadata import GetWaitingMetadataUseCase
from skiller.application.use_cases.handle_input import HandleInputUseCase
from skiller.application.use_cases.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.list_webhooks import ListWebhooksUseCase
from skiller.application.use_cases.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.remove_webhook import RemoveWebhookUseCase
from skiller.application.use_cases.render_current_step import RenderCurrentStepUseCase
from skiller.application.use_cases.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.resume_run import ResumeRunUseCase
from skiller.domain.large_result_truncator import LargeResultTruncator
from skiller.infrastructure.config.settings import Settings, get_settings
from skiller.infrastructure.db.sqlite_execution_output_store import SqliteExecutionOutputStore
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.llm.minimax_llm import MinimaxLLM
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP
from skiller.infrastructure.tools.shell.default_shell import DefaultShellRunner


@dataclass(frozen=True)
class RuntimeContainer:
    settings: Settings
    runtime_service: RuntimeApplicationService
    query_service: RunQueryService


def build_runtime_container(
    settings: Settings | None = None,
    *,
    skills_dir: str = "skills",
) -> RuntimeContainer:
    cfg = settings or get_settings()
    store = SqliteStateStore(cfg.db_path)
    execution_output_store = SqliteExecutionOutputStore(cfg.db_path)
    webhook_registry = SqliteWebhookRegistry(cfg.db_path)
    skill_runner = FilesystemSkillRunner(skills_dir=skills_dir)
    llm = _build_llm(cfg)
    mcp = DefaultMCP()
    shell = DefaultShellRunner()
    large_result_truncator = LargeResultTruncator()

    bootstrap_runtime_use_case = BootstrapRuntimeUseCase(
        store=store,
        execution_output_store=execution_output_store,
        webhook_registry=webhook_registry,
    )

    create_run_use_case = CreateRunUseCase(store, skill_runner)
    append_runtime_event_use_case = AppendRuntimeEventUseCase(store)
    complete_run_use_case = CompleteRunUseCase(store)
    fail_run_use_case = FailRunUseCase(store)
    get_start_step_use_case = GetStartStepUseCase(store=store)
    handle_input_use_case = HandleInputUseCase(store=store)
    handle_webhook_use_case = HandleWebhookUseCase(store=store)
    list_webhooks_use_case = ListWebhooksUseCase(registry=webhook_registry)
    register_webhook_use_case = RegisterWebhookUseCase(registry=webhook_registry)
    remove_webhook_use_case = RemoveWebhookUseCase(registry=webhook_registry)

    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_llm_prompt_step_use_case = ExecuteLlmPromptStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        llm=llm,
        large_result_truncator=large_result_truncator,
    )
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        mcp=mcp,
        large_result_truncator=large_result_truncator,
    )
    execute_notify_step_use_case = ExecuteNotifyStepUseCase(store=store)
    execute_shell_step_use_case = ExecuteShellStepUseCase(
        store=store,
        execution_output_store=execution_output_store,
        shell=shell,
        large_result_truncator=large_result_truncator,
    )
    execute_switch_step_use_case = ExecuteSwitchStepUseCase(store=store)
    execute_when_step_use_case = ExecuteWhenStepUseCase(store=store)
    execute_wait_input_step_use_case = ExecuteWaitInputStepUseCase(store=store)
    execute_wait_webhook_step_use_case = ExecuteWaitWebhookStepUseCase(store=store)
    resume_run_use_case = ResumeRunUseCase(store=store)
    get_run_status_use_case = GetRunStatusUseCase(store)
    get_run_logs_use_case = GetRunLogsUseCase(store)
    get_runs_use_case = GetRunsUseCase(store)
    get_execution_output_use_case = GetExecutionOutputUseCase(execution_output_store)
    get_waiting_metadata_use_case = GetWaitingMetadataUseCase(
        store=store,
        skill_runner=skill_runner,
    )
    run_worker_service = RunWorkerService(
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        append_runtime_event_use_case=append_runtime_event_use_case,
        render_current_step_use_case=render_current_step_use_case,
        render_mcp_config_use_case=render_mcp_config_use_case,
        execute_assign_step_use_case=execute_assign_step_use_case,
        execute_llm_prompt_step_use_case=execute_llm_prompt_step_use_case,
        execute_mcp_step_use_case=execute_mcp_step_use_case,
        execute_notify_step_use_case=execute_notify_step_use_case,
        execute_shell_step_use_case=execute_shell_step_use_case,
        execute_switch_step_use_case=execute_switch_step_use_case,
        execute_when_step_use_case=execute_when_step_use_case,
        execute_wait_input_step_use_case=execute_wait_input_step_use_case,
        execute_wait_webhook_step_use_case=execute_wait_webhook_step_use_case,
    )
    query_service = RunQueryService(
        get_execution_output_use_case=get_execution_output_use_case,
        get_run_status_use_case=get_run_status_use_case,
        get_run_logs_use_case=get_run_logs_use_case,
        get_runs_use_case=get_runs_use_case,
        get_waiting_metadata_use_case=get_waiting_metadata_use_case,
    )

    runtime_service = RuntimeApplicationService(
        bootstrap_runtime_use_case=bootstrap_runtime_use_case,
        append_runtime_event_use_case=append_runtime_event_use_case,
        create_run_use_case=create_run_use_case,
        fail_run_use_case=fail_run_use_case,
        get_start_step_use_case=get_start_step_use_case,
        handle_input_use_case=handle_input_use_case,
        handle_webhook_use_case=handle_webhook_use_case,
        list_webhooks_use_case=list_webhooks_use_case,
        register_webhook_use_case=register_webhook_use_case,
        remove_webhook_use_case=remove_webhook_use_case,
        resume_run_use_case=resume_run_use_case,
        get_run_status_use_case=get_run_status_use_case,
        run_worker_service=run_worker_service,
    )
    return RuntimeContainer(
        settings=cfg,
        runtime_service=runtime_service,
        query_service=query_service,
    )


def _build_llm(settings: Settings) -> NullLLM | FakeLLM | MinimaxLLM:
    provider = settings.llm_provider.strip().lower()

    if provider == "null":
        return NullLLM()

    if provider == "fake":
        return FakeLLM(
            response_json=settings.fake_llm_response_json,
            model=settings.fake_llm_model,
        )

    if provider == "minimax":
        return MinimaxLLM(
            api_key=settings.minimax_api_key,
            base_url=settings.minimax_base_url,
            model=settings.minimax_model,
            timeout_seconds=settings.minimax_timeout_seconds,
        )

    raise ValueError(
        f"Unsupported AGENT_LLM_PROVIDER='{settings.llm_provider}'. "
        "Use 'null', 'fake' or 'minimax'."
    )
