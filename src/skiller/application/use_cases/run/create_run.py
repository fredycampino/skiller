import uuid
from typing import Any

from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.skill_runner_port import SkillRunnerPort
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import SkillSource
from skiller.domain.step.skill_step_model import validate_skill_snapshot


class CreateRunUseCase:
    def __init__(self, store: RunStorePort, skill_runner: SkillRunnerPort) -> None:
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
        raw_skill = self.skill_runner.load_skill(skill_source, skill_ref)
        try:
            skill_snapshot = validate_skill_snapshot(raw_skill)
        except ValueError as exc:
            raise ValueError(f"Invalid skill format for '{skill_ref}'. {exc}") from exc
        context = RunContext(inputs=inputs, step_executions={})
        return self.store.create_run(
            skill_source,
            skill_ref,
            skill_snapshot,
            context,
            run_id=run_id,
        )
