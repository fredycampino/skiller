from typing import Any, Protocol

from runtime.domain.models import RunStatus


class StateStorePort(Protocol):
    def init_db(self) -> None:
        ...

    def create_run(self, skill_name: str, context: dict[str, Any]) -> str:
        ...

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        current_step: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ...

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        ...

    def append_event(self, event_type: str, payload: dict[str, Any], run_id: str | None = None) -> str:
        ...

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        ...

    def create_wait(
        self,
        run_id: str,
        wait_key: str,
        match: dict[str, Any],
        *,
        step_id: str | None = None,
        expires_at: str | None = None,
    ) -> str:
        ...

    def resolve_wait(self, wait_id: str) -> None:
        ...

    def find_matching_waits(self, wait_key: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        ...
