from skiller.application.ports.external_event_store_port import ExternalEventStorePort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.wait_store_port import WaitStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.match_type import MatchType
from skiller.domain.run_model import RunStatus
from skiller.domain.source_type import SourceType
from skiller.domain.step_execution_model import StepExecution, WaitChannelOutput
from skiller.domain.wait_type import WaitType


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
        channel_event = self.external_event_store.get_latest_external_event(
            source_type=SourceType.CHANNEL,
            source_name=channel,
            match_type=MatchType.CHANNEL_KEY,
            match_key=key,
            since_created_at=current_step.run_created_at,
        )

        if channel_event is not None:
            channel_event_id = str(channel_event.get("id", "")).strip()
            if not channel_event_id:
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
