from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stui.port.session_store_port import StoredSession

_SESSION_FILE_NAME = "session.json"


@dataclass(frozen=True)
class FileSessionStoreAdapter:
    path: Path

    def read(self) -> StoredSession | None:
        try:
            data = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        if not isinstance(data, dict):
            return None
        return _to_stored_session(data)

    def write(self, session: StoredSession) -> None:
        run_id = session.run_id.strip()
        if not run_id:
            self.clear()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run_id,
            "run_name": session.run_name.strip(),
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=True, indent=2))

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return


def default_session_store_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if config_home:
        return Path(config_home).expanduser() / "skiller" / "stui" / _SESSION_FILE_NAME
    return Path.home() / ".config" / "skiller" / "stui" / _SESSION_FILE_NAME


def _to_stored_session(data: dict[str, Any]) -> StoredSession | None:
    run_id = data.get("run_id")
    if not isinstance(run_id, str):
        return None
    normalized_run_id = run_id.strip()
    if not normalized_run_id:
        return None
    run_name = data.get("run_name", "")
    if not isinstance(run_name, str):
        run_name = ""
    return StoredSession(run_id=normalized_run_id, run_name=run_name.strip())
