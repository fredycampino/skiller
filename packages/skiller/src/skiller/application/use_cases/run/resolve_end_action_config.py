from dataclasses import dataclass
from typing import Any

from skiller.application.action.action_uid_factory import ActionUidFactory
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
    def __init__(self, runner: RunnerPort, uid_factory: ActionUidFactory) -> None:
        self.runner = runner
        self.uid_factory = uid_factory

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
        action_payload = dict(rendered_action)
        action_payload["uid"] = self.uid_factory.new_uid()

        try:
            action = action_from_dict(action_payload)
        except ValueError:
            return ResolveEndActionConfig(action=None)

        if not isinstance(action, RunAction):
            return ResolveEndActionConfig(action=None)

        return ResolveEndActionConfig(action=action)
