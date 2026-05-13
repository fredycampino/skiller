from __future__ import annotations

from dataclasses import dataclass, field

from stui.adapter.cli_run_adapter import CliRunAdapter
from stui.port.run_port import RunDispatch, RunRuntimeStatus


@dataclass
class DefaultRunPort:
    command_adapter: CliRunAdapter = field(default_factory=CliRunAdapter)

    def run(self, raw_args: str) -> RunDispatch:
        return self.command_adapter.run(raw_args)

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        return self.command_adapter.status(run_id)
