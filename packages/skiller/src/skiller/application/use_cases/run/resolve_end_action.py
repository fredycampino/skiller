from dataclasses import dataclass

from skiller.application.use_cases.run.resolve_end_action_config import (
    ResolveEndActionConfigParser,
)
from skiller.domain.action.action_model import EndActionTrigger, RunAction
from skiller.domain.run.run_store_port import RunStorePort


@dataclass(frozen=True)
class ResolveEndActionInput:
    run_id: str
    trigger: EndActionTrigger


@dataclass(frozen=True)
class ResolveEndActionResult:
    action: RunAction | None


class ResolveEndActionUseCase:
    def __init__(
        self,
        *,
        store: RunStorePort,
        config_parser: ResolveEndActionConfigParser,
    ) -> None:
        self.store = store
        self.config_parser = config_parser

    def execute(self, request: ResolveEndActionInput) -> ResolveEndActionResult:
        run = self.store.get_run(request.run_id)
        if run is None:
            return ResolveEndActionResult(action=None)

        config = self.config_parser.parse(
            run=run,
            trigger=request.trigger,
        )
        if config.action is None:
            return ResolveEndActionResult(action=None)

        return ResolveEndActionResult(action=config.action)
