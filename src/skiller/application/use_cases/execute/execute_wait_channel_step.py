from datetime import datetime, timezone

from skiller.application.ports.external_event_store_port import ExternalEventStorePort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.wait_store_port import WaitStorePort
from skiller.application.use_cases.render.render_current_step import CurrentStep
from skiller.application.use_cases.shared.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.run.run_model import RunStatus
from skiller.domain.step.step_execution_model import StepExecution, WaitChannelOutput
from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_type import WaitType


class ExecuteWaitChannelStepUseCase:
    def __init__(
        self,
        run_store: RunStorePort,
        wait_store: WaitStorePort,
        external_event_store: ExternalEventStorePort,
    ) -> None:
        self.run_store = run_store
        self.wait_store = wait_store
        self.external_event_store = external_event_store

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step = current_step.step
        step_id = current_step.step_id
        channel = str(step.get("channel", "")).strip()
        key = str(step.get("key", "")).strip()

        if not channel:
            raise ValueError(f"Step '{step_id}' requires channel")
        if not key:
            raise ValueError(f"Step '{step_id}' requires key")

        active_wait = self.wait_store.get_active_wait(
            current_step.run_id,
            step_id,
            wait_type=WaitType.CHANNEL,
        )
        if active_wait is None:
            self.wait_store.create_wait(
                current_step.run_id,
                step_id=step_id,
                wait_type=WaitType.CHANNEL,
                source_type=SourceType.CHANNEL,
                source_name=channel,
                match_type=MatchType.CHANNEL_KEY,
                match_key=key,
            )
            self.run_store.update_run(
                current_step.run_id,
                status=RunStatus.WAITING,
                current=step_id,
                context=current_step.context,
            )
            return StepAdvance(
                status=StepExecutionStatus.WAITING,
                execution=StepExecution(
                    step_type=current_step.step_type,
                    input={"channel": channel, "key": key},
                    evaluation={},
                    output=WaitChannelOutput(
                        text=f"Waiting channel: {channel}:{key}.",
                        channel=channel,
                        key=key,
                    ),
                ),
            )

        wait_created_at = str(active_wait.get("created_at", "")).strip()
        channel_event = self.external_event_store.get_latest_external_event(
            source_type=SourceType.CHANNEL,
            source_name=channel,
            match_type=MatchType.CHANNEL_KEY,
            match_key=key,
            since_created_at=wait_created_at or current_step.run_created_at,
        )

        if channel_event is not None:
            channel_event_id = str(channel_event.get("id", "")).strip()
            if not channel_event_id:
                channel_event = None
            elif not _is_channel_event_fresh_for_wait(
                channel_event=channel_event,
                active_wait=active_wait,
            ):
                self.external_event_store.consume_external_event(
                    channel_event_id,
                    run_id=current_step.run_id,
                )
                channel_event = None
            elif not self.external_event_store.consume_external_event(
                channel_event_id,
                run_id=current_step.run_id,
            ):
                channel_event = None

        if channel_event is not None:
            payload = channel_event.get("payload")
            if not isinstance(payload, dict):
                payload = None
            resolved_key = key
            if isinstance(payload, dict):
                resolved_key = str(payload.get("key", "")).strip()
            execution = StepExecution(
                step_type=current_step.step_type,
                input={"channel": channel, "key": key},
                evaluation={},
                output=WaitChannelOutput(
                    text=f"Channel message received: {channel}:{resolved_key}.",
                    channel=channel,
                    key=resolved_key,
                    payload=payload,
                ),
            )
            current_step.context.step_executions[step_id] = execution
            if active_wait is not None:
                self.wait_store.resolve_wait(str(active_wait["id"]))

            raw_next = step.get("next")
            if raw_next is None:
                self.run_store.update_run(
                    current_step.run_id,
                    status=RunStatus.RUNNING,
                    context=current_step.context,
                )
                return StepAdvance(
                    status=StepExecutionStatus.COMPLETED,
                    execution=execution,
                )

            next_step_id = str(raw_next).strip()
            if not next_step_id:
                raise ValueError(f"Step '{step_id}' requires non-empty next")

            self.run_store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                current=next_step_id,
                context=current_step.context,
            )
            return StepAdvance(
                status=StepExecutionStatus.NEXT,
                next_step_id=next_step_id,
                execution=execution,
            )

        self.run_store.update_run(
            current_step.run_id,
            status=RunStatus.WAITING,
            current=step_id,
            context=current_step.context,
        )
        return StepAdvance(
            status=StepExecutionStatus.WAITING,
            execution=StepExecution(
                step_type=current_step.step_type,
                input={"channel": channel, "key": key},
                evaluation={},
                output=WaitChannelOutput(
                    text=f"Waiting channel: {channel}:{key}.",
                    channel=channel,
                    key=key,
                ),
            ),
        )


def _is_channel_event_fresh_for_wait(
    *,
    channel_event: dict[str, object],
    active_wait: dict[str, object],
) -> bool:
    payload = channel_event.get("payload")
    if not isinstance(payload, dict):
        return True
    message_timestamp = _payload_timestamp_epoch(payload)
    if message_timestamp is None:
        return True
    wait_created_at = _created_at_epoch(active_wait)
    if wait_created_at is None:
        return True
    return message_timestamp >= wait_created_at


def _payload_timestamp_epoch(payload: dict[str, object]) -> float | None:
    raw_timestamp = payload.get("timestamp")
    if raw_timestamp is None:
        return None
    try:
        timestamp = float(raw_timestamp)
    except (TypeError, ValueError):
        return None
    if timestamp > 10_000_000_000:
        return timestamp / 1000
    return timestamp


def _created_at_epoch(row: dict[str, object]) -> float | None:
    raw_created_at = str(row.get("created_at", "")).strip()
    if not raw_created_at:
        return None
    normalized = raw_created_at.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()
