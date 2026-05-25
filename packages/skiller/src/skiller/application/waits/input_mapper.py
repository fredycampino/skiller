from typing import Any

from skiller.application.use_cases.ingress.handle_input import (
    HandleInputInput,
    HandleInputResult,
)


class InputWaitMapper:
    def to_handle_input(
        self,
        run_id: str,
        *,
        text: str,
    ) -> HandleInputInput:
        return HandleInputInput(
            run_id=run_id.strip(),
            text=text.strip(),
        )

    def to_handle_dict(
        self,
        request: HandleInputInput,
        result: HandleInputResult,
    ) -> dict[str, Any]:
        payload = {
            "accepted": result.accepted,
            "run_id": request.run_id,
            "matched_runs": result.run_ids,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload
