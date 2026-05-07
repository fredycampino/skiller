from __future__ import annotations

from dataclasses import dataclass

from skiller.interfaces.tui.adapter.default_runs_port import DefaultRunsPort
from skiller.interfaces.tui.port.runs_port import RunsPortItem


@dataclass
class FakeRunsAdapter:
    called_with: tuple[int, tuple[str, ...] | None] | None = None

    def list_runs(
        self,
        *,
        limit: int = 20,
        statuses: list[str] | None = None,
    ) -> list[RunsPortItem]:
        self.called_with = (limit, tuple(statuses) if statuses is not None else None)
        return [
            RunsPortItem(
                id="run-1",
                skill_source="internal",
                skill_ref="chat",
                status="WAITING",
                current="ask_user",
                created_at="2026-05-04 00:00:00",
                updated_at="2026-05-04 00:00:00",
            )
        ]


def test_default_runs_port_delegates_to_command_adapter() -> None:
    adapter = FakeRunsAdapter()
    port = DefaultRunsPort(command_adapter=adapter)

    result = port.list_runs(limit=7, statuses=["WAITING"])

    assert result == [
        RunsPortItem(
            id="run-1",
            skill_source="internal",
            skill_ref="chat",
            status="WAITING",
            current="ask_user",
            created_at="2026-05-04 00:00:00",
            updated_at="2026-05-04 00:00:00",
        )
    ]
    assert adapter.called_with == (7, ("WAITING",))
