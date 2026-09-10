from typing import Any

from skiller.application.observations.models import (
    ObserveEvent,
    ObserveFrameKind,
    ObserveIdle,
    ObserveRunInput,
    ObserveRunResult,
    ObserveRunSettings,
    ObserveStart,
    ObserveStop,
    ObserveWait,
    ObserveWaitType,
)


class ObserveRunMapper:
    def __init__(self, settings: ObserveRunSettings) -> None:
        self.settings = settings

    def to_observe_input(
        self,
        run_id: str,
        *,
        after: int | None,
        tail: int | None,
    ) -> ObserveRunInput:
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise ValueError("RUN_ID is required")
        if after is not None and after < 0:
            raise ValueError("--after must be greater than or equal to 0")

        normalized_tail = self.settings.default_tail if tail is None else tail
        if normalized_tail < 1 or normalized_tail > self.settings.max_tail:
            raise ValueError(f"--tail must be between 1 and {self.settings.max_tail}")

        return ObserveRunInput(
            run_id=normalized_run_id,
            after=after,
            tail=normalized_tail,
        )

    def to_frame(self, result: ObserveRunResult) -> dict[str, Any] | None:
        if isinstance(result, ObserveIdle):
            return None
        if isinstance(result, ObserveStart):
            return {
                "kind": ObserveFrameKind.START.value,
                "version": 1,
                "run_id": result.run_id,
                "requested_after": result.requested_after,
                "effective_after": result.effective_after,
                "last_sequence": result.last_sequence,
                "tail": result.tail,
                "truncated": result.truncated,
            }
        if isinstance(result, ObserveEvent):
            return {
                "kind": ObserveFrameKind.EVENT.value,
                "event": result.event.model_dump(mode="json"),
            }
        if isinstance(result, ObserveWait):
            frame: dict[str, Any] = {
                "kind": ObserveFrameKind.WAIT.value,
                "sequence": result.sequence,
                "wait_type": result.wait_type.value,
            }
            if result.wait_type == ObserveWaitType.INPUT and result.prompt:
                frame["prompt"] = result.prompt
            return frame
        if isinstance(result, ObserveStop):
            return {
                "kind": ObserveFrameKind.STOP.value,
                "sequence": result.sequence,
                "status": result.status.value.lower(),
            }
        raise TypeError(f"Unsupported observe result '{type(result).__name__}'")
