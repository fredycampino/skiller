from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.step.server_status_port import ServerStatusPort
from skiller.domain.step.step_type import StepType
from skiller.domain.tool.channel_sender_port import ChannelSenderPort


class FlowReadinessCheckStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(frozen=True)
class FlowReadinessCheckError:
    code: str
    message: str


@dataclass(frozen=True)
class FlowReadinessCheckResult:
    status: FlowReadinessCheckStatus
    errors: list[FlowReadinessCheckError]


class FlowReadinessCheckerUseCase:
    def __init__(
        self,
        runner: RunnerPort,
        server_status: ServerStatusPort,
        channel_sender: ChannelSenderPort,
    ) -> None:
        self.runner = runner
        self.server_status = server_status
        self.channel_sender = channel_sender

    def execute(
        self,
        flow_ref: str,
        *,
        flow_source: str,
    ) -> FlowReadinessCheckResult:
        raw_flow = self.runner.load(flow_source, flow_ref)
        raw_steps = raw_flow["steps"]
        server_required_step = self._find_server_required_step(raw_steps)
        channel_required_step = self._find_channel_required_step(raw_steps)

        if server_required_step is not None and not self.server_status.is_available():
            return self._invalid(
                code="FLOW_SERVER_UNAVAILABLE",
                message=(
                    "FLOW_SERVER_UNAVAILABLE: flow requires local server for "
                    f"{server_required_step['step_type']} (step={server_required_step['step_id']})"
                ),
            )

        if (
            channel_required_step is not None
            and not self.channel_sender.is_available(channel=channel_required_step["channel"])
        ):
            return self._invalid(
                code="FLOW_WHATSAPP_UNAVAILABLE",
                message=(
                    "FLOW_WHATSAPP_UNAVAILABLE: flow requires configured WhatsApp channel sender "
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

    def _valid(self) -> FlowReadinessCheckResult:
        return FlowReadinessCheckResult(
            status=FlowReadinessCheckStatus.VALID,
            errors=[],
        )

    def _invalid(
        self,
        *,
        code: str,
        message: str,
    ) -> FlowReadinessCheckResult:
        return FlowReadinessCheckResult(
            status=FlowReadinessCheckStatus.INVALID,
            errors=[FlowReadinessCheckError(code=code, message=message)],
        )
