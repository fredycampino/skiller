from dataclasses import dataclass

from runtime.application.ports.bootstrap import RuntimeBootstrapPort
from runtime.application.ports.run_query import RunQueryPort
from runtime.application.ports.runtime import RuntimePort
from runtime.application.query_service import RunQueryService
from runtime.application.runtime import Runtime
from runtime.application.use_cases.bootstrap_runtime import BootstrapRuntimeUseCase
from runtime.application.use_cases.execute_run import ExecuteRunUseCase
from runtime.application.use_cases.event_loop import EventLoopUseCase
from runtime.application.use_cases.get_run_logs import GetRunLogsUseCase
from runtime.application.use_cases.get_run_status import GetRunStatusUseCase
from runtime.application.use_cases.handle_webhook import HandleWebhookUseCase
from runtime.application.use_cases.process_event import ProcessEventUseCase
from runtime.application.use_cases.start_run import StartRunUseCase
from runtime.config.settings import Settings, get_settings
from runtime.domain.policies import PolicyGate
from runtime.infrastructure.bus.in_memory_bus import EventBus
from runtime.infrastructure.db.sqlite_store import StateStore
from runtime.skills.loader import SkillRunner
from runtime.tools.registry import ToolRouter


@dataclass(frozen=True)
class RuntimeContainer:
    settings: Settings
    bootstrap: RuntimeBootstrapPort
    runtime: RuntimePort
    query: RunQueryPort


def build_runtime_container(settings: Settings | None = None, *, skills_dir: str = "skills") -> RuntimeContainer:
    cfg = settings or get_settings()
    store = StateStore(cfg.db_path)
    event_bus = EventBus()
    tool_router = ToolRouter()
    skill_runner = SkillRunner(skills_dir=skills_dir)
    policy_gate = PolicyGate()
    bootstrap_use_case = BootstrapRuntimeUseCase(store)

    start_run_use_case = StartRunUseCase(store)
    handle_webhook_use_case = HandleWebhookUseCase()
    execute_run_use_case = ExecuteRunUseCase(
        store=store,
        skill_runner=skill_runner,
        policy_gate=policy_gate,
        tool_router=tool_router,
    )
    process_event_use_case = ProcessEventUseCase(
        store=store,
        execute_run_use_case=execute_run_use_case,
    )
    event_loop_use_case = EventLoopUseCase(
        event_bus=event_bus,
        process_event_use_case=process_event_use_case,
    )
    get_run_status_use_case = GetRunStatusUseCase(store)
    get_run_logs_use_case = GetRunLogsUseCase(store)
    query_service = RunQueryService(
        get_run_status_use_case=get_run_status_use_case,
        get_run_logs_use_case=get_run_logs_use_case,
    )

    runtime = Runtime(
        store=store,
        event_bus=event_bus,
        tool_router=tool_router,
        skill_runner=skill_runner,
        policy_gate=policy_gate,
        start_run_use_case=start_run_use_case,
        handle_webhook_use_case=handle_webhook_use_case,
        execute_run_use_case=execute_run_use_case,
        process_event_use_case=process_event_use_case,
        event_loop_use_case=event_loop_use_case,
    )
    return RuntimeContainer(
        settings=cfg,
        bootstrap=bootstrap_use_case,
        runtime=runtime,
        query=query_service,
    )
