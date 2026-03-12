from dataclasses import dataclass

from skiller.application.query_service import RunQueryService
from skiller.application.runtime_application_service import RuntimeApplicationService
from skiller.application.runtime_bootstrap_service import RuntimeBootstrapService
from skiller.application.use_cases.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.application.use_cases.complete_run import CompleteRunUseCase
from skiller.application.use_cases.execute_assign_step import ExecuteAssignStepUseCase
from skiller.application.use_cases.execute_llm_prompt_step import ExecuteLlmPromptStepUseCase
from skiller.application.use_cases.execute_mcp_step import ExecuteMcpStepUseCase
from skiller.application.use_cases.execute_notify_step import ExecuteNotifyStepUseCase
from skiller.application.use_cases.execute_switch_step import ExecuteSwitchStepUseCase
from skiller.application.use_cases.execute_when_step import ExecuteWhenStepUseCase
from skiller.application.use_cases.execute_wait_webhook_step import ExecuteWaitWebhookStepUseCase
from skiller.application.use_cases.fail_run import FailRunUseCase
from skiller.application.use_cases.get_run_logs import GetRunLogsUseCase
from skiller.application.use_cases.get_run_status import GetRunStatusUseCase
from skiller.application.use_cases.get_start_step import GetStartStepUseCase
from skiller.application.use_cases.handle_webhook import HandleWebhookUseCase
from skiller.application.use_cases.render_current_step import RenderCurrentStepUseCase
from skiller.application.use_cases.register_webhook import RegisterWebhookUseCase
from skiller.application.use_cases.render_mcp_config import RenderMcpConfigUseCase
from skiller.application.use_cases.remove_webhook import RemoveWebhookUseCase
from skiller.application.use_cases.resume_run import ResumeRunUseCase
from skiller.application.use_cases.start_run import StartRunUseCase
from skiller.infrastructure.config.settings import Settings, get_settings
from skiller.infrastructure.db.sqlite_state_store import SqliteStateStore
from skiller.infrastructure.db.sqlite_webhook_registry import SqliteWebhookRegistry
from skiller.infrastructure.llm.fake_llm import FakeLLM
from skiller.infrastructure.llm.minimax_llm import MinimaxLLM
from skiller.infrastructure.llm.null_llm import NullLLM
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner
from skiller.infrastructure.tools.mcp.default_mcp import DefaultMCP


@dataclass(frozen=True)
class RuntimeContainer:
    settings: Settings
    bootstrap_service: RuntimeBootstrapService
    runtime_service: RuntimeApplicationService
    query_service: RunQueryService


def build_runtime_container(
    settings: Settings | None = None,
    *,
    skills_dir: str = "skills",
) -> RuntimeContainer:
    cfg = settings or get_settings()
    store = SqliteStateStore(cfg.db_path)
    webhook_registry = SqliteWebhookRegistry(cfg.db_path)
    skill_runner = FilesystemSkillRunner(skills_dir=skills_dir)
    llm = _build_llm(cfg)
    mcp = DefaultMCP()

    bootstrap_use_case = BootstrapRuntimeUseCase(store)
    bootstrap_service = RuntimeBootstrapService(bootstrap_runtime_use_case=bootstrap_use_case)

    start_run_use_case = StartRunUseCase(store, skill_runner)
    complete_run_use_case = CompleteRunUseCase(store)
    fail_run_use_case = FailRunUseCase(store)
    get_start_step_use_case = GetStartStepUseCase(store=store)
    handle_webhook_use_case = HandleWebhookUseCase(store=store)
    register_webhook_use_case = RegisterWebhookUseCase(registry=webhook_registry)
    remove_webhook_use_case = RemoveWebhookUseCase(registry=webhook_registry)

    render_current_step_use_case = RenderCurrentStepUseCase(store=store, skill_runner=skill_runner)
    render_mcp_config_use_case = RenderMcpConfigUseCase(store=store, skill_runner=skill_runner)
    execute_assign_step_use_case = ExecuteAssignStepUseCase(store=store)
    execute_llm_prompt_step_use_case = ExecuteLlmPromptStepUseCase(store=store, llm=llm)
    execute_mcp_step_use_case = ExecuteMcpStepUseCase(store=store, mcp=mcp)
    execute_notify_step_use_case = ExecuteNotifyStepUseCase(store=store)
    execute_switch_step_use_case = ExecuteSwitchStepUseCase(store=store)
    execute_when_step_use_case = ExecuteWhenStepUseCase(store=store)
    execute_wait_webhook_step_use_case = ExecuteWaitWebhookStepUseCase(store=store)
    resume_run_use_case = ResumeRunUseCase(store=store)
    get_run_status_use_case = GetRunStatusUseCase(store)
    get_run_logs_use_case = GetRunLogsUseCase(store)
    query_service = RunQueryService(
        get_run_status_use_case=get_run_status_use_case,
        get_run_logs_use_case=get_run_logs_use_case,
    )

    runtime_service = RuntimeApplicationService(
        start_run_use_case=start_run_use_case,
        complete_run_use_case=complete_run_use_case,
        fail_run_use_case=fail_run_use_case,
        get_start_step_use_case=get_start_step_use_case,
        render_current_step_use_case=render_current_step_use_case,
        render_mcp_config_use_case=render_mcp_config_use_case,
        execute_assign_step_use_case=execute_assign_step_use_case,
        execute_llm_prompt_step_use_case=execute_llm_prompt_step_use_case,
        execute_mcp_step_use_case=execute_mcp_step_use_case,
        execute_notify_step_use_case=execute_notify_step_use_case,
        execute_switch_step_use_case=execute_switch_step_use_case,
        execute_when_step_use_case=execute_when_step_use_case,
        execute_wait_webhook_step_use_case=execute_wait_webhook_step_use_case,
        handle_webhook_use_case=handle_webhook_use_case,
        register_webhook_use_case=register_webhook_use_case,
        remove_webhook_use_case=remove_webhook_use_case,
        resume_run_use_case=resume_run_use_case,
        get_run_status_use_case=get_run_status_use_case,
    )
    return RuntimeContainer(
        settings=cfg,
        bootstrap_service=bootstrap_service,
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
        f"Unsupported AGENT_LLM_PROVIDER='{settings.llm_provider}'. Use 'null', 'fake' or 'minimax'."
    )
