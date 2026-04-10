from typing import Protocol

from skiller.domain.match_type import MatchType
from skiller.domain.source_type import SourceType


class ExternalEventStorePort(Protocol):
    def create_external_event(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        payload: dict[str, object],
        run_id: str | None = None,
        step_id: str | None = None,
        external_id: str | None = None,
        dedup_key: str | None = None,
    ) -> str: ...

    def get_latest_external_event(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        run_id: str | None = None,
        step_id: str | None = None,
        since_created_at: str | None = None,
    ) -> dict[str, object] | None: ...

    def register_external_receipt(
        self,
        dedup_key: str,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
        payload: dict[str, object],
    ) -> bool: ...

    def consume_external_event(
        self,
        event_id: str,
        *,
        run_id: str,
    ) -> bool: ...
