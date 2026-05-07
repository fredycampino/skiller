from typing import Any, Protocol


class ExecutionOutputStorePort(Protocol):
    def init_db(self) -> None: ...

    def store_execution_output(
        self,
        *,
        run_id: str,
        step_id: str,
        output_body: dict[str, Any],
    ) -> str: ...

    def get_execution_output(self, body_ref: str) -> dict[str, Any] | None: ...
