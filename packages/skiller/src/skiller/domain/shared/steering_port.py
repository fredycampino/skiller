from typing import Protocol

from skiller.domain.run.steering_model import SteeringItem, SteeringItemType


class SteeringPort(Protocol):
    def append(self, run_id: str, item: SteeringItem) -> None: ...

    def pop(self, run_id: str, item_type: SteeringItemType) -> list[SteeringItem]: ...
