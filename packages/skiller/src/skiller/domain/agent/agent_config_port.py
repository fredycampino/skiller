from typing import Protocol

from skiller.domain.agent.agent_config_model import AgentConfig


class AgentConfigPort(Protocol):
    def get_config(self) -> AgentConfig:
        raise NotImplementedError
