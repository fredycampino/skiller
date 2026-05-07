from typing import Protocol

from skiller.domain.run.steering_model import SteeringItem


class AgentSteeringPort(Protocol):
    def enqueue(self, run_id: str, item: SteeringItem) -> None: ...

    def consume_abort_turn(self, run_id: str) -> bool: ...

    def pop_steering_messages(self, run_id: str) -> list[str]: ...
