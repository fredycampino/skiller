from typing import Protocol

from skiller.domain.match_type import MatchType
from skiller.domain.source_type import SourceType
from skiller.domain.wait_type import WaitType


class WaitStorePort(Protocol):
    def create_wait(
        self,
        run_id: str,
        *,
        step_id: str,
        wait_type: WaitType,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
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

    def find_matching_waits(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
    ) -> list[dict[str, object]]: ...

    def expire_active_waits_for_run(self, run_id: str) -> int: ...
