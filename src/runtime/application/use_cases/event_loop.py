from runtime.application.ports.event_bus import EventBusPort
from runtime.application.use_cases.process_event import ProcessEventUseCase


class EventLoopUseCase:
    def __init__(self, event_bus: EventBusPort, process_event_use_case: ProcessEventUseCase) -> None:
        self.event_bus = event_bus
        self.process_event_use_case = process_event_use_case

    def execute(self) -> list[str]:
        resumed_runs: list[str] = []
        while True:
            event = self.event_bus.consume()
            if event is None:
                break
            resumed_runs.extend(self.process_event_use_case.execute(event))
        return resumed_runs
