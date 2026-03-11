from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.application.ports.skill_runner_port import SkillRunnerPort
from skiller.application.ports.state_store_port import StateStorePort
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import RunStatus


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


class StepType(str, Enum):
    ASSIGN = "assign"
    NOTIFY = "notify"
    MCP = "mcp"
    LLM_PROMPT = "llm_prompt"
    WAIT_WEBHOOK = "wait_webhook"


@dataclass(frozen=True)
class CurrentStep:
    run_id: str
    step_index: int
    step_id: str
    step_type: StepType
    step: dict[str, Any]
    context: RunContext


@dataclass(frozen=True)
class RenderCurrentStepResult:
    status: CurrentStepStatus
    current_step: CurrentStep | None = None


class RenderCurrentStepUseCase:
    def __init__(self, store: StateStorePort, skill_runner: SkillRunnerPort) -> None:
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
        if not isinstance(raw_steps, list):
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)

        current = run.current
        if current is None:
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)

        step_index, raw_step = self._find_step(raw_steps, current)
        if raw_step is None:
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_SKILL)

        step = self.skill_runner.render_step(raw_step, run.context.to_dict())
        if not isinstance(step, dict):
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_STEP)

        step_id = str(step.get("id", f"step_{step_index}"))
        raw_step_type = str(step.get("type", "")).strip()
        try:
            step_type = StepType(raw_step_type)
        except ValueError:
            return RenderCurrentStepResult(status=CurrentStepStatus.INVALID_STEP)

        return RenderCurrentStepResult(
            status=CurrentStepStatus.READY,
            current_step=CurrentStep(
                run_id=run_id,
                step_index=step_index,
                step_id=step_id,
                step_type=step_type,
                step=step,
                context=run.context,
            ),
        )

    def _find_step(self, raw_steps: list[object], step_id: str) -> tuple[int, dict[str, Any] | None]:
        match_index = -1
        match_step: dict[str, Any] | None = None

        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, dict):
                return -1, None

            candidate_id = str(raw_step.get("id", "")).strip()
            if candidate_id != step_id:
                continue

            if match_step is not None:
                return -1, None

            match_index = index
            match_step = raw_step

        return match_index, match_step
