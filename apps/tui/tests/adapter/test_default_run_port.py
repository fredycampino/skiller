from __future__ import annotations

from dataclasses import dataclass

from stui.adapter.default_run_port import DefaultRunPort
from stui.port.run_port import RunDispatch, RunRuntimeStatus


@dataclass
class FakeCommandAdapter:
    def run(self, raw_args: str) -> RunDispatch:
        raise AssertionError(f"unexpected run call: {raw_args}")

    def status(self, run_id: str) -> RunRuntimeStatus | None:
        _ = run_id
        return None


def test_default_run_port_delegates_status_lookup() -> None:
    port = DefaultRunPort(command_adapter=FakeCommandAdapter())

    assert port.status("run-1234") is None
