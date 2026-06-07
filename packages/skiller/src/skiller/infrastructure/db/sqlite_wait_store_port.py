from skiller.domain.wait.match_type import MatchType
from skiller.domain.wait.source_type import SourceType
from skiller.domain.wait.wait_store_port import WaitStorePort
from skiller.domain.wait.wait_type import WaitType
from skiller.infrastructure.db.datasource.sqlite_wait_datasource import SqliteWaitDatasource


class SqliteWaitStorePort(WaitStorePort):
    def __init__(self, datasource: SqliteWaitDatasource) -> None:
        self.datasource = datasource

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
    ) -> str:
        return self.datasource.create_wait(
            run_id,
            step_id=step_id,
            wait_type=wait_type,
            source_type=source_type,
            source_name=source_name,
            match_type=match_type,
            match_key=match_key,
            expires_at=expires_at,
        )

    def resolve_wait(self, wait_id: str) -> None:
        self.datasource.resolve_wait(wait_id)

    def get_active_wait(
        self,
        run_id: str,
        step_id: str,
        *,
        wait_type: WaitType,
    ) -> dict[str, object] | None:
        return self.datasource.get_active_wait(
            run_id,
            step_id,
            wait_type=wait_type,
        )

    def find_matching_waits(
        self,
        *,
        source_type: SourceType,
        source_name: str,
        match_type: MatchType,
        match_key: str,
    ) -> list[dict[str, object]]:
        return self.datasource.find_matching_waits(
            source_type=source_type,
            source_name=source_name,
            match_type=match_type,
            match_key=match_key,
        )

    def expire_active_waits_for_run(self, run_id: str) -> int:
        return self.datasource.expire_active_waits_for_run(run_id)
