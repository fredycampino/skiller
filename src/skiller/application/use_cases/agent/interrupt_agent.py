from dataclasses import dataclass
from enum import Enum

from skiller.application.ports.agent.agent_steering_port import AgentSteeringPort
from skiller.application.ports.persistence.run_store_port import RunStorePort
from skiller.domain.run.steering_model import SteeringAction, SteeringItem, SteeringTarget


class InterruptAgentStatus(str, Enum):
    ENQUEUED = "ENQUEUED"
    INVALID_RUN_ID = "INVALID_RUN_ID"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"


@dataclass(frozen=True)
class InterruptAgentResult:
    status: InterruptAgentStatus
    run_id: str
    item: SteeringItem | None = None
    error: str | None = None


class InterruptAgentUseCase:
    def __init__(
        self,
        store: RunStorePort,
        agent_steering: AgentSteeringPort,
    ) -> None:
        self.store = store
        self.agent_steering = agent_steering

    def execute(self, run_id: str) -> InterruptAgentResult:
        normalized = run_id.strip()
        if not normalized:
            return InterruptAgentResult(
                status=InterruptAgentStatus.INVALID_RUN_ID,
                run_id=run_id,
                error="run_id is required",
            )

        run = self.store.get_run(normalized)
        if run is None:
            return InterruptAgentResult(
                status=InterruptAgentStatus.RUN_NOT_FOUND,
                run_id=normalized,
                error=f"Run '{normalized}' not found",
            )

        item = SteeringItem(
            target=SteeringTarget.AGENT,
            action=SteeringAction.ABORT_TURN,
        )
        self.agent_steering.enqueue(normalized, item)
        return InterruptAgentResult(
            status=InterruptAgentStatus.ENQUEUED,
            run_id=normalized,
            item=item,
        )
