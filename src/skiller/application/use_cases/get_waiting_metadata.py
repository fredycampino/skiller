from typing import Any

from skiller.application.ports.skill_runner_port import SkillRunnerPort
from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.run_model import RunStatus
from skiller.domain.skill_step_model import find_skill_step
from skiller.domain.step_type import StepType


class GetWaitingMetadataUseCase:
    def __init__(self, store: StateStorePort, skill_runner: SkillRunnerPort) -> None:
        self.store = store
        self.skill_runner = skill_runner

    def execute(self, run_id: str) -> dict[str, Any] | None:
        run = self.store.get_run(run_id)
        if run is None:
            return None
        if run.status != RunStatus.WAITING.value:
            return None
        if run.current is None:
            return None

        skill = run.skill_snapshot
        if not isinstance(skill, dict):
            return None

        raw_steps = skill.get("steps", [])

        try:
            _, parsed_step = find_skill_step(raw_steps, run.current)
        except ValueError:
            return None

        step = self.skill_runner.render_step(parsed_step.body, run.context.to_dict())
        if not isinstance(step, dict):
            return None

        if parsed_step.step_type == StepType.WAIT_WEBHOOK:
            webhook = str(step.get("webhook", "")).strip()
            key = str(step.get("key", "")).strip()
            if not webhook or not key:
                return None
            return {
                "wait_type": "webhook",
                "webhook": webhook,
                "key": key,
            }

        if parsed_step.step_type == StepType.WAIT_INPUT:
            prompt = str(step.get("prompt", "")).strip()
            if not prompt:
                return None
            return {
                "wait_type": "input",
                "prompt": prompt,
            }

        return None
