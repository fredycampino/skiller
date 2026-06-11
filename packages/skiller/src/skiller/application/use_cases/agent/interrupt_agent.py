from dataclasses import dataclass
from enum import Enum

from skiller.domain.run.run_model import RunStatus
from skiller.domain.run.run_store_port import RunStorePort
from skiller.domain.run.steering_model import SteeringAgentInterrupt, SteeringItem
from skiller.domain.shared.steering_port import SteeringPort


class InterruptAgentStatus(str, Enum):
    ENQUEUED = "ENQUEUED"
    INVALID_RUN_ID = "INVALID_RUN_ID"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    NOT_RUNNING = "NOT_RUNNING"


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
        steering: SteeringPort,
    ) -> None:
        self.store = store
        self.steering = steering

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
        if run.status != RunStatus.RUNNING.value:
            return InterruptAgentResult(
                status=InterruptAgentStatus.NOT_RUNNING,
                run_id=normalized,
                error=f"Run '{normalized}' is not running",
            )

        item = SteeringAgentInterrupt()
        self.steering.append(normalized, item)
        return InterruptAgentResult(
            status=InterruptAgentStatus.ENQUEUED,
            run_id=normalized,
            item=item,
        )
