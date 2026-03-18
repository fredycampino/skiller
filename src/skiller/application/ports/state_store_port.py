from typing import Protocol

from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import Run, RunStatus


class StateStorePort(Protocol):
    def init_db(self) -> None: ...

    def create_run(
        self,
        skill_source: str,
        skill_ref: str,
        skill_snapshot: dict[str, object],
        context: RunContext,
        *,
        run_id: str,
    ) -> str: ...

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        current: str | None = None,
        context: RunContext | None = None,
    ) -> None: ...

    def get_run(self, run_id: str) -> Run | None: ...

    def append_event(
        self, event_type: str, payload: dict[str, object], run_id: str | None = None
    ) -> str: ...

    def list_events(self, run_id: str) -> list[dict[str, object]]: ...

    def create_wait(
        self,
        run_id: str,
        webhook: str,
        key: str,
        *,
        step_id: str | None = None,
        expires_at: str | None = None,
    ) -> str: ...

    def resolve_wait(self, wait_id: str) -> None: ...

    def get_active_wait(self, run_id: str, step_id: str) -> dict[str, object] | None: ...

    def find_matching_waits(self, webhook: str, key: str) -> list[dict[str, object]]: ...

    def create_webhook_event(
        self,
        webhook: str,
        key: str,
        payload: dict[str, object],
        dedup_key: str,
    ) -> str: ...

    def create_input_wait(self, run_id: str, step_id: str) -> str: ...

    def resolve_input_wait(self, wait_id: str) -> None: ...

    def get_active_input_wait(self, run_id: str, step_id: str) -> dict[str, object] | None: ...

    def create_input_event(
        self,
        run_id: str,
        step_id: str,
        payload: dict[str, object],
    ) -> str: ...

    def get_latest_input_event(
        self,
        run_id: str,
        step_id: str,
        *,
        since_created_at: str | None = None,
    ) -> dict[str, object] | None: ...

    def get_latest_webhook_event(
        self,
        webhook: str,
        key: str,
        *,
        since_created_at: str | None = None,
    ) -> dict[str, object] | None: ...

    def register_webhook_receipt(
        self,
        dedup_key: str,
        webhook: str,
        key: str,
        payload: dict[str, object],
    ) -> bool: ...

    def expire_active_waits_for_run(self, run_id: str) -> int: ...
