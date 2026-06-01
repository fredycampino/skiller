from pathlib import Path

import pytest

from skiller.application.use_cases.flow.flow_checker import FlowCheckerUseCase, FlowCheckStatus
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner

pytestmark = pytest.mark.integration


def test_all_builtin_agents_pass_flow_checker() -> None:
    runner = FilesystemSkillRunner(
        skills_dir="packages/skiller/agents",
    )
    checker = FlowCheckerUseCase(runner=runner)

    failures: list[str] = []
    for agent_path in sorted(Path("packages/skiller/agents").glob("*/agent.yaml")):
        result = checker.execute(agent_path.parent.name, flow_source="internal")
        if result.status == FlowCheckStatus.VALID:
            continue
        messages = "\n".join(f"- {item.message}" for item in result.errors)
        failures.append(f"{agent_path.parent.name}\n{messages}")

    assert not failures, "Builtin agents failed checker:\n\n" + "\n\n".join(failures)
