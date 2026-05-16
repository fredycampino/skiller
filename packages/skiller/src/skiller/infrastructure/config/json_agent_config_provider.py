import json
from collections.abc import Mapping
from pathlib import Path

from skiller.domain.agent.agent_config_model import AgentConfig
from skiller.domain.agent.agent_config_port import AgentConfigPort
from skiller.infrastructure.config.agent_config_adapter import agent_config_from_json


class JsonAgentConfigProvider(AgentConfigPort):
    def __init__(
        self,
        *,
        config_path: Path,
        env: Mapping[str, str],
    ) -> None:
        self.config_path = config_path
        self.env = env

    def get_config(self) -> AgentConfig:
        return agent_config_from_json(
            self._load_config(),
            env=self.env,
        )

    def _load_config(self) -> dict[str, object]:
        config_path = self.config_path.expanduser()
        if not config_path.exists():
            raise RuntimeError(f"Missing agent config file: {_display_path(config_path)}")
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Invalid JSON config file: {_display_path(config_path)} "
                f"(line {exc.lineno}, column {exc.colno})"
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"Config file must contain a JSON object: {config_path}")
        return payload


def _display_path(path: Path) -> str:
    expanded = path.expanduser()
    home = Path.home()
    try:
        relative = expanded.relative_to(home)
        return f"~/{relative}"
    except ValueError:
        return str(expanded)
