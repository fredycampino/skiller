from pathlib import Path
from typing import Protocol

from skiller.domain.agent.agent_config_model import AgentConfig
from skiller.domain.agent.agent_config_validation_model import AgentConfigValidation


class AgentConfigPort(Protocol):
    def get_config(self, *, config_path: Path | None = None) -> AgentConfig:
        raise NotImplementedError

    def validate_config(self, *, config_path: Path | None = None) -> AgentConfigValidation:
        raise NotImplementedError
