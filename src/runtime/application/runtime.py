from typing import Any

from runtime.application.ports.event_bus import EventBusPort
from runtime.application.ports.policy_gate import PolicyGatePort
from runtime.application.ports.skill_runner import SkillRunnerPort
from runtime.application.ports.state_store import StateStorePort
from runtime.application.ports.tool_executor import ToolExecutorPort
from runtime.application.use_cases.execute_run import ExecuteRunUseCase
from runtime.application.use_cases.event_loop import EventLoopUseCase
from runtime.application.use_cases.handle_webhook import HandleWebhookUseCase
from runtime.application.use_cases.process_event import ProcessEventUseCase
from runtime.application.use_cases.start_run import StartRunUseCase
from runtime.domain.policies import PolicyGate
from runtime.infrastructure.bus.in_memory_bus import EventBus
from runtime.skills.loader import SkillRunner
from runtime.tools.registry import ToolRouter


class Runtime:
    def __init__(
        self,
        store: StateStorePort,
        skills_dir: str = "skills",
        event_bus: EventBusPort | None = None,
        tool_router: ToolExecutorPort | None = None,
        skill_runner: SkillRunnerPort | None = None,
        policy_gate: PolicyGatePort | None = None,
        start_run_use_case: StartRunUseCase | None = None,
        handle_webhook_use_case: HandleWebhookUseCase | None = None,
        execute_run_use_case: ExecuteRunUseCase | None = None,
        process_event_use_case: ProcessEventUseCase | None = None,
        event_loop_use_case: EventLoopUseCase | None = None,
    ) -> None:
        self.store = store
        self.event_bus = event_bus or EventBus()
        self.tool_router = tool_router or ToolRouter()
        self.skill_runner = skill_runner or SkillRunner(skills_dir=skills_dir)
        self.policy_gate = policy_gate or PolicyGate()
        self.start_run_use_case = start_run_use_case or StartRunUseCase(store)
        self.handle_webhook_use_case = handle_webhook_use_case or HandleWebhookUseCase()
        self.execute_run_use_case = execute_run_use_case or ExecuteRunUseCase(
            store=store,
            skill_runner=self.skill_runner,
            policy_gate=self.policy_gate,
            tool_router=self.tool_router,
        )
        self.process_event_use_case = process_event_use_case or ProcessEventUseCase(
            store=store,
            execute_run_use_case=self.execute_run_use_case,
        )
        self.event_loop_use_case = event_loop_use_case or EventLoopUseCase(
            event_bus=self.event_bus,
            process_event_use_case=self.process_event_use_case,
        )

    def start_run(self, skill_name: str, inputs: dict[str, Any]) -> str:
        run_id, event = self.start_run_use_case.execute(skill_name, inputs)
        self.event_bus.publish(event)
        self.event_loop_use_case.execute()
        return run_id

    def handle_webhook(self, wait_key: str, payload: dict[str, Any]) -> list[str]:
        event = self.handle_webhook_use_case.execute(wait_key, payload)
        self.event_bus.publish(event)
        return self.event_loop_use_case.execute()
