import uuid
from dataclasses import dataclass
from typing import Any

from skiller.domain.step.run_step_model import parse_run_steps
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.step.step_type import StepType
from skiller.domain.step.template_resolution_error import UnresolvedTemplateError
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_store_port import WaitStorePort


@dataclass(frozen=True)
class CheckWebhookWaitInput:
    skill_source: str
    skill_ref: str
    inputs: dict[str, Any]


@dataclass(frozen=True)
class WebhookWaitConflict:
    run_id: str
    webhook: str
    key: str


@dataclass(frozen=True)
class CheckWebhookWaitResult:
    conflict: WebhookWaitConflict | None


@dataclass(frozen=True)
class _CheckFlowReference:
    id: str
    source: str
    ref: str


class CheckWebhookWaitUseCase:
    def __init__(self, wait_store: WaitStorePort, skill_runner: RunnerPort) -> None:
        self.wait_store = wait_store
        self.skill_runner = skill_runner

    def execute(self, request: CheckWebhookWaitInput) -> CheckWebhookWaitResult:
        raw_skill = self.skill_runner.load(request.skill_source, request.skill_ref)
        raw_steps = raw_skill.get("steps", [])
        rendered_context = {"inputs": request.inputs, "step_executions": {}}
        flow = _CheckFlowReference(
            id=str(uuid.uuid4()),
            source=request.skill_source,
            ref=request.skill_ref,
        )

        for run_step in parse_run_steps(raw_steps):
            if run_step.step_type != StepType.WAIT_WEBHOOK:
                continue
            try:
                step = self.skill_runner.render(
                    run_step.body,
                    rendered_context,
                    flow=flow,
                )
            except UnresolvedTemplateError:
                continue
            webhook = str(step.get("webhook", "")).strip()
            key = str(step.get("key", "")).strip()
            if not webhook or not key or "{{" in webhook or "{{" in key:
                continue

            waits = self.wait_store.find_matching_waits(
                source_type=SourceType.WEBHOOK,
                source_name=webhook,
                match_type=MatchType.SIGNAL,
                match_key=key,
            )
            if waits:
                existing_run_id = str(waits[0].get("run_id", "")).strip()
                if existing_run_id:
                    return CheckWebhookWaitResult(
                        conflict=WebhookWaitConflict(
                            run_id=existing_run_id,
                            webhook=webhook,
                            key=key,
                        )
                    )

        return CheckWebhookWaitResult(conflict=None)
