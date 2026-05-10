from pathlib import Path

import pytest
from skiller.application.use_cases.skill.skill_checker import SkillCheckerUseCase, SkillCheckStatus
from skiller.infrastructure.db.sqlite_execution_output_store import SqliteExecutionOutputStore
from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner

pytestmark = pytest.mark.integration


def test_all_builtin_agents_pass_skill_checker(tmp_path: Path) -> None:
    execution_output_store = SqliteExecutionOutputStore(str(tmp_path / "test.db"))
    execution_output_store.init_db()
    skill_runner = FilesystemSkillRunner(
        skills_dir="packages/skiller/agents",
        execution_output_store=execution_output_store,
    )
    checker = SkillCheckerUseCase(skill_runner=skill_runner)

    failures: list[str] = []
    for agent_path in sorted(Path("packages/skiller/agents").glob("*/agent.yaml")):
        result = checker.execute(agent_path.parent.name, skill_source="internal")
        if result.status == SkillCheckStatus.VALID:
            continue
        messages = "\n".join(f"- {item.message}" for item in result.errors)
        failures.append(f"{agent_path.parent.name}\n{messages}")

    assert not failures, "Builtin agents failed checker:\n\n" + "\n\n".join(failures)
