from dataclasses import dataclass
from typing import TypeAlias

from skiller.domain.run.run_model import Run, RunStatus
from skiller.domain.step.run_step_model import find_run_step
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.step.step_type import StepType


@dataclass(frozen=True, kw_only=True)
class InputWaitingMetadata:
    prompt: str


@dataclass(frozen=True, kw_only=True)
class WebhookWaitingMetadata:
    webhook: str
    key: str


@dataclass(frozen=True, kw_only=True)
class ChannelWaitingMetadata:
    channel: str
    key: str


WaitingMetadata: TypeAlias = (
    InputWaitingMetadata | WebhookWaitingMetadata | ChannelWaitingMetadata
)


class WaitingMetadataResolver:
    def __init__(self, runner: RunnerPort) -> None:
        self.runner = runner

    def resolve(self, run: Run) -> WaitingMetadata | None:
        if run.status != RunStatus.WAITING.value or run.current is None:
            return None

        snapshot = run.snapshot
        if not isinstance(snapshot, dict):
            return None

        try:
            _, parsed_step = find_run_step(snapshot.get("steps", []), run.current)
        except ValueError:
            return None

        rendered_step = self.runner.render(
            parsed_step.body,
            run.context.to_dict(),
            flow=run,
        )
        if not isinstance(rendered_step, dict):
            return None

        if parsed_step.step_type == StepType.WAIT_INPUT:
            prompt = str(rendered_step.get("prompt", "")).strip()
            if prompt:
                return InputWaitingMetadata(prompt=prompt)
            return None

        if parsed_step.step_type == StepType.WAIT_WEBHOOK:
            webhook = str(rendered_step.get("webhook", "")).strip()
            key = str(rendered_step.get("key", "")).strip()
            if webhook and key:
                return WebhookWaitingMetadata(webhook=webhook, key=key)
            return None

        if parsed_step.step_type == StepType.WAIT_CHANNEL:
            channel = str(rendered_step.get("channel", "")).strip()
            key = str(rendered_step.get("key", "")).strip()
            if channel and key:
                return ChannelWaitingMetadata(channel=channel, key=key)

        return None
