import uuid
from typing import Any

from skiller.application.ports.skill_runner_port import SkillRunnerPort
from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import SkillSource


class StartRunUseCase:
    def __init__(self, store: StateStorePort, skill_runner: SkillRunnerPort) -> None:
        self.store = store
        self.skill_runner = skill_runner

    def execute(
        self,
        skill_ref: str,
        inputs: dict[str, Any],
        *,
        skill_source: str = SkillSource.INTERNAL.value,
        param_run_id: str | None = None,
    ) -> str:
        normalized_run_id = self._normalize_run_id(param_run_id)
        skill_snapshot = self.skill_runner.load_skill(skill_source, skill_ref)
        if not isinstance(skill_snapshot, dict):
            raise ValueError(f"Invalid skill format for '{skill_ref}'. Expected an object.")
        context = RunContext(inputs=inputs, results={})
        return self.store.create_run(
            skill_source,
            skill_ref,
            skill_snapshot,
            context,
            run_id=normalized_run_id,
        )

    def _normalize_run_id(self, param_run_id: str | None) -> str:
        if param_run_id is None:
            return str(uuid.uuid4())

        run_id = param_run_id.strip()
        if not run_id:
            raise ValueError("Run id must be a non-empty string")

        try:
            return str(uuid.UUID(run_id))
        except ValueError as exc:
            raise ValueError("Run id must be a valid UUID") from exc
