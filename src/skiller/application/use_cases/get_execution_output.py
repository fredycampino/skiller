from typing import Any

from skiller.application.ports.execution_output_store_port import ExecutionOutputStorePort


class GetExecutionOutputUseCase:
    def __init__(self, execution_output_store: ExecutionOutputStorePort) -> None:
        self.execution_output_store = execution_output_store

    def execute(self, body_ref: str) -> dict[str, Any] | None:
        normalized = body_ref.strip()
        if not normalized:
            raise ValueError("body_ref is required")
        return self.execution_output_store.get_execution_output(normalized)
