from dataclasses import dataclass

from skiller.domain.action.action_model import EndActionTrigger
from skiller.domain.run.run_store_port import RunStorePort


@dataclass(frozen=True)
class ResolveCleanupInput:
    run_id: str
    trigger: EndActionTrigger


@dataclass(frozen=True)
class ResolveCleanupResult:
    cleanup: bool
    cleaned: bool


class ResolveCleanupUseCase:
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def execute(self, request: ResolveCleanupInput) -> ResolveCleanupResult:
        run = self.store.get_run(request.run_id)
        if run is None:
            return ResolveCleanupResult(cleanup=False, cleaned=False)

        raw_config = run.snapshot.get(request.trigger.value)
        if not isinstance(raw_config, dict):
            return ResolveCleanupResult(cleanup=False, cleaned=False)

        cleanup = raw_config.get("cleanup") is True
        if not cleanup:
            return ResolveCleanupResult(cleanup=False, cleaned=False)

        cleaned = self.store.cleanup_run(request.run_id)
        return ResolveCleanupResult(cleanup=True, cleaned=cleaned)
