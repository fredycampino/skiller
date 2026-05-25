from typing import Any

from skiller.application.use_cases.ingress.handle_channel import (
    HandleChannelInput,
    HandleChannelResult,
)


class ChannelWaitMapper:
    def to_handle_input(
        self,
        channel: str,
        key: str,
        payload: dict[str, Any],
        *,
        external_id: str | None = None,
        dedup_key: str | None = None,
    ) -> HandleChannelInput:
        return HandleChannelInput(
            channel=channel.strip(),
            key=key.strip(),
            payload=payload,
            external_id=external_id,
            dedup_key=(dedup_key or "").strip(),
        )

    def to_handle_dict(
        self,
        request: HandleChannelInput,
        result: HandleChannelResult,
    ) -> dict[str, Any]:
        response = {
            "accepted": result.accepted,
            "duplicate": result.duplicate,
            "channel": request.channel,
            "key": request.key,
            "matched_runs": result.run_ids,
        }
        if request.external_id is not None:
            response["external_id"] = request.external_id
        if result.error is not None:
            response["error"] = result.error
        return response
