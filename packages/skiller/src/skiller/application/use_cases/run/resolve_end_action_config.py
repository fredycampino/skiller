from dataclasses import dataclass
from typing import Any

from skiller.domain.action.action_model import (
    EndActionTrigger,
    RunAction,
    action_from_dict,
)
from skiller.domain.run.run_context_model import RunContext
from skiller.domain.step.runner_port import RunnerPort


@dataclass(frozen=True)
class ResolveEndActionConfig:
    action: RunAction | None


class ResolveEndActionConfigParser:
    def __init__(self, runner: RunnerPort) -> None:
        self.runner = runner

    def parse(
        self,
        *,
        snapshot: dict[str, Any],
        context: RunContext,
        trigger: EndActionTrigger,
    ) -> ResolveEndActionConfig:
        raw_config = snapshot.get(trigger.value)
        if not isinstance(raw_config, dict):
            return ResolveEndActionConfig(action=None)

        raw_action = raw_config.get("action")
        if not isinstance(raw_action, dict):
            return ResolveEndActionConfig(action=None)

        rendered_action = self.runner.render(raw_action, context.to_dict())
        if not isinstance(rendered_action, dict):
            return ResolveEndActionConfig(action=None)

        try:
            action = action_from_dict(rendered_action)
        except ValueError:
            return ResolveEndActionConfig(action=None)

        if not isinstance(action, RunAction):
            return ResolveEndActionConfig(action=None)

        return ResolveEndActionConfig(action=action)
