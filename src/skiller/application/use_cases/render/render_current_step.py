from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.skill_runner_port import SkillRunnerPort
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.skill_step_model import find_skill_step
from skiller.domain.step.step_type import StepType


class CurrentStepStatus(str, Enum):
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    READY = "READY"
    DONE = "DONE"
    CANCELLED = RunStatus.CANCELLED.value
    WAITING = RunStatus.WAITING.value
    SUCCEEDED = RunStatus.SUCCEEDED.value
    FAILED = RunStatus.FAILED.value
    INVALID_SKILL = "INVALID_SKILL"
    INVALID_STEP = "INVALID_STEP"


@dataclass(frozen=True)
class CurrentStep:
    run_id: str
    step_index: int
    step_id: str
    step_type: StepType
    step: dict[str, Any]
    context: RunContext
    run_created_at: str | None = None


@dataclass(frozen=True)
class RenderCurrentStepResult:
    status: CurrentStepStatus
    current_step: CurrentStep | None = None


class RenderCurrentStepUseCase:
    def __init__(self, store: RunStorePort, skill_runner: SkillRunnerPort) -> None:
        self.store = store
        self.skill_runner = skill_runner

    def execute(self, run_id: str) -> RenderCurrentStepResult:
        run = self.store.get_run(run_id)
        if run is None:
            return RenderCurrentStepResult(status=CurrentStepStatus.RUN_NOT_FOUND)

        if run.status == RunStatus.CANCELLED.value:
            return RenderCurrentStepResult(status=CurrentStepStatus.CANCELLED)

        if run.status == RunStatus.WAITING.value:
            return RenderCurrentStepResult(status=CurrentStepStatus.WAITING)

        if run.status == RunStatus.SUCCEEDED.value:
            return RenderCurrentStepResult(status=CurrentStepStatus.SUCCEEDED)

        if run.status == RunStatus.FAILED.value:
            return RenderCurrentStepResult(status=CurrentStepStatus.FAILED)

        skill = run.skill_snapshot
        if not isinstance(skill, dict):
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)

        raw_steps = skill.get("steps", [])

        current = run.current
        if current is None:
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)

        try:
            step_index, parsed_step = find_skill_step(raw_steps, current)
        except ValueError:
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)

        step = self.skill_runner.render_step(parsed_step.body, run.context.to_dict())
        if not isinstance(step, dict):
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_STEP)

        return RenderCurrentStepResult(
            status=CurrentStepStatus.READY,
            current_step=CurrentStep(
                run_id=run_id,
                step_index=step_index,
                step_id=parsed_step.step_id,
                step_type=parsed_step.step_type,
                step=step,
                context=run.context,
                run_created_at=run.created_at,
            ),
        )
