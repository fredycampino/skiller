from typing import Protocol

from skiller.domain.external_event_type import ExternalEventType
from skiller.domain.run_context_model import RunContext
from skiller.domain.run_model import Run, RunStatus
from skiller.domain.wait_type import WaitType


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
        *,
        step_id: str,
        wait_type: WaitType,
        webhook: str | None = None,
        key: str | None = None,
        expires_at: str | None = None,
    ) -> str: ...

    def resolve_wait(self, wait_id: str) -> None: ...

    def get_active_wait(
        self,
        run_id: str,
        step_id: str,
        *,
        wait_type: WaitType,
    ) -> dict[str, object] | None: ...

    def find_matching_waits(self, webhook: str, key: str) -> list[dict[str, object]]: ...

    def create_external_event(
        self,
        *,
        event_type: ExternalEventType,
        payload: dict[str, object],
        run_id: str | None = None,
        step_id: str | None = None,
        webhook: str | None = None,
        key: str | None = None,
        dedup_key: str | None = None,
    ) -> str: ...

    def get_latest_external_event(
        self,
        *,
        event_type: ExternalEventType,
        run_id: str | None = None,
        step_id: str | None = None,
        webhook: str | None = None,
        key: str | None = None,
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
