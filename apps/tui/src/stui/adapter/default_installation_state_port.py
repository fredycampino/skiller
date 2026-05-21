from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from stui.port.installation_state_port import InstallationState


@dataclass(frozen=True)
class DefaultInstallationStatePort:
    home: Path = field(default_factory=Path.home)
    cwd: Path = field(default_factory=Path.cwd)
    environment: Mapping[str, str] = field(default_factory=lambda: os.environ)

    def read(self) -> InstallationState:
        db_path = self._runtime_db_path()
        agent_config_path = self._agent_config_path()
        return InstallationState(
            runtime_db_exists=db_path.exists(),
            agent_config_exists=agent_config_path.exists(),
        )

    def _runtime_db_path(self) -> Path:
        explicit_db_path = self.environment.get("AGENT_DB_PATH", "").strip()
        if explicit_db_path:
            return self._resolve_path(explicit_db_path)

        config = self._read_runtime_config()
        configured_db_path = _value_at(config, ("runtime", "db_path"))
        if configured_db_path is not None:
            return self._resolve_path(str(configured_db_path).strip())

        return self.cwd / "runtime.db"

    def _agent_config_path(self) -> Path:
        explicit_agent_path = self.environment.get("AGENT_AGENT_CONFIG_FILE", "").strip()
        if explicit_agent_path:
            return self._resolve_path(explicit_agent_path)

        local_agent_path = self.cwd / "agent.json"
        if local_agent_path.exists():
            return local_agent_path

        return self.home / ".skiller" / "settings" / "agent.json"

    def _read_runtime_config(self) -> dict[str, object]:
        explicit_config_path = self.environment.get("AGENT_CONFIG_FILE", "").strip()
        if explicit_config_path:
            config_path = self._resolve_path(explicit_config_path)
        else:
            config_path = self.home / ".skiller" / "settings" / "config.json"

        if not config_path.exists():
            return {}

        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        return payload

    def _resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return self.cwd / path


def _value_at(config: dict[str, object], path: tuple[str, ...]) -> object | None:
    value: object = config
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
