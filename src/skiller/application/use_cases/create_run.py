import uuid
from typing import Any

from skiller.application.ports.skill_runner_port import SkillRunnerPort
from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import SkillSource


class CreateRunUseCase:
    def __init__(self, store: StateStorePort, skill_runner: SkillRunnerPort) -> None:
        self.store = store
        self.skill_runner = skill_runner

    def execute(
        self,
        skill_ref: str,
        inputs: dict[str, Any],
        *,
        skill_source: str = SkillSource.INTERNAL.value,
    ) -> str:
        run_id = str(uuid.uuid4())
        skill_snapshot = self.skill_runner.load_skill(skill_source, skill_ref)
        if not isinstance(skill_snapshot, dict):
            raise ValueError(f"Invalid skill format for '{skill_ref}'. Expected an object.")
        context = RunContext(inputs=inputs, results={})
        return self.store.create_run(
            skill_source,
            skill_ref,
            skill_snapshot,
            context,
            run_id=run_id,
        )
