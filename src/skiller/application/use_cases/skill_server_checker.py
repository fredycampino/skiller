from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.application.ports.channel_sender_port import ChannelSenderPort
from skiller.application.ports.server_status_port import ServerStatusPort
from skiller.application.ports.skill_runner_port import SkillRunnerPort
from skiller.domain.step_type import StepType


class SkillServerCheckStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(frozen=True)
class SkillServerCheckError:
    code: str
    message: str


@dataclass(frozen=True)
class SkillServerCheckResult:
    status: SkillServerCheckStatus
    errors: list[SkillServerCheckError]


class SkillServerCheckerUseCase:
    def __init__(
        self,
        skill_runner: SkillRunnerPort,
        server_status: ServerStatusPort,
        channel_sender: ChannelSenderPort,
    ) -> None:
        self.skill_runner = skill_runner
        self.server_status = server_status
        self.channel_sender = channel_sender

    def execute(
        self,
        skill_ref: str,
        *,
        skill_source: str,
    ) -> SkillServerCheckResult:
        raw_skill = self.skill_runner.load_skill(skill_source, skill_ref)
        raw_steps = raw_skill["steps"]
        server_required_step = self._find_server_required_step(raw_steps)
        channel_required_step = self._find_channel_required_step(raw_steps)

        if server_required_step is not None and not self.server_status.is_available():
            return self._invalid(
                code="SKILL_SERVER_UNAVAILABLE",
                message=(
                    "SKILL_SERVER_UNAVAILABLE: skill requires local server for "
                    f"{server_required_step['step_type']} (step={server_required_step['step_id']})"
                ),
            )

        if (
            channel_required_step is not None
            and not self.channel_sender.is_available(channel=channel_required_step["channel"])
        ):
            return self._invalid(
                code="SKILL_WHATSAPP_UNAVAILABLE",
                message=(
                    "SKILL_WHATSAPP_UNAVAILABLE: skill requires active WhatsApp bridge "
                    f"for {channel_required_step['step_type']} "
                    f"(step={channel_required_step['step_id']})"
                ),
            )

        return self._valid()

    def _find_server_required_step(self, raw_steps: list[Any]) -> dict[str, str] | None:
        for raw_step in raw_steps:
            for step_type in (StepType.WAIT_CHANNEL.value, StepType.WAIT_WEBHOOK.value):
                if step_type not in raw_step:
                    continue
                step_id = str(raw_step.get(step_type, "")).strip()
                if step_id:
                    return {
                        "step_type": step_type,
                        "step_id": step_id,
                    }
        return None

    def _find_channel_required_step(self, raw_steps: list[Any]) -> dict[str, str] | None:
        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                continue

            for step_type in (StepType.WAIT_CHANNEL.value, StepType.SEND.value):
                if step_type not in raw_step:
                    continue

                channel = str(raw_step.get("channel", "")).strip().lower()
                if channel != "whatsapp":
                    continue

                step_id = str(raw_step.get(step_type, "")).strip()
                if step_id:
                    return {
                        "step_type": step_type,
                        "step_id": step_id,
                        "channel": channel,
                    }

        return None

    def _valid(self) -> SkillServerCheckResult:
        return SkillServerCheckResult(
            status=SkillServerCheckStatus.VALID,
            errors=[],
        )

    def _invalid(
        self,
        *,
        code: str,
        message: str,
    ) -> SkillServerCheckResult:
        return SkillServerCheckResult(
            status=SkillServerCheckStatus.INVALID,
            errors=[SkillServerCheckError(code=code, message=message)],
        )
