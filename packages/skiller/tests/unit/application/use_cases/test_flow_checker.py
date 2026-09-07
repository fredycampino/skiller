from pathlib import Path

import pytest

from skiller.application.use_cases.flow.flow_check_model import FlowCheckStatus
from skiller.application.use_cases.flow.flow_checker import FlowCheckerUseCase
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper

pytestmark = pytest.mark.unit


class _FakeFlowPort:
    def __init__(self, raw_flow: object) -> None:
        self.raw_flow = raw_flow
        self.calls: list[Path] = []
        self.mapper = FlowYamlMapper()

    def get_yaml_flow(self, flow_path: Path):
        self.calls.append(flow_path)
        return self.mapper.to_flow(self.raw_flow)


def test_flow_checker_accepts_valid_flow_and_uses_flow_port() -> None:
    port = _FakeFlowPort(
        {
            "name": "diagnostics",
            "start": "inspect_shell",
            "steps": [
                {
                    "shell": "inspect_shell",
                    "command": 'python3 -c "print(42)"',
                    "next": "summarize_output",
                },
                {
                    "notify": "summarize_output",
                    "message": '{{output_value("inspect_shell").stderr}}',
                },
            ],
        }
    )

    flow_path = Path("/flows/diagnostics.yaml")
    result = FlowCheckerUseCase(flow_port=port).execute(flow_path)

    assert port.calls == [flow_path]
    assert result.status == FlowCheckStatus.VALID
    assert result.errors == []


def test_flow_checker_returns_shape_errors_without_collecting_steps() -> None:
    result = FlowCheckerUseCase(flow_port=_FakeFlowPort(["bad"])).execute(Path("/flows/demo.yaml"))

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["FLOW_FORMAT_INVALID"]
