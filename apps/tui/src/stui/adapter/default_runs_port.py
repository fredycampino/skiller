from __future__ import annotations

from dataclasses import dataclass, field

from stui.adapter.cli_runs_adapter import CliRunsAdapter
from stui.port.runs_port import RunsPortItem


@dataclass
class DefaultRunsPort:
    command_adapter: CliRunsAdapter = field(default_factory=CliRunsAdapter)

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[RunsPortItem]:
        return self.command_adapter.list_runs(limit=limit, statuses=statuses)
