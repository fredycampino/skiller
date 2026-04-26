from __future__ import annotations

from dataclasses import dataclass, field

from skiller.interfaces.tui.adapter.cli_run_adapter import CliRunAdapter
from skiller.interfaces.tui.adapter.polling_event_observer import PollingEventObserver
from skiller.interfaces.tui.port.run_port import CommandAck, RunObserver


@dataclass
class DefaultRunPort:
    command_adapter: CliRunAdapter = field(default_factory=CliRunAdapter)
    event_observer: PollingEventObserver = field(default_factory=PollingEventObserver)

    def run(self, raw_args: str) -> CommandAck:
        return self.command_adapter.run(raw_args)

    def subscribe(self, observer: RunObserver) -> None:
        self.event_observer.subscribe(observer)

    def unsubscribe(self, observer: RunObserver) -> None:
        self.event_observer.unsubscribe(observer)
