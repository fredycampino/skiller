from pathlib import Path

import pytest

from skiller.application.use_cases.flow.flow_checker import FlowCheckerUseCase, FlowCheckStatus
from skiller.infrastructure.flow.filesystem_flow_port import FilesystemFlowPort
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper

pytestmark = pytest.mark.integration


def test_all_packaged_flows_pass_flow_checker() -> None:
    flow_paths = sorted(Path("apps/agents").rglob("*.yaml"))
    assert flow_paths, "Expected at least one packaged flow in apps/agents"

    flow_port = FilesystemFlowPort(mapper=FlowYamlMapper())
    checker = FlowCheckerUseCase(flow_port=flow_port)

    failures: list[str] = []
    for flow_path in flow_paths:
        result = checker.execute(flow_path)
        if result.status == FlowCheckStatus.VALID:
            continue
        messages = "\n".join(f"- {item.message}" for item in result.errors)
        failures.append(f"{flow_path}\n{messages}")

    assert not failures, "Packaged flows failed checker:\n\n" + "\n\n".join(failures)
