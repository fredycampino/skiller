import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from skiller.infrastructure.config.settings_source import (
    load_config,
    load_development_env,
    resolve_json_config_path,
)


class JsonRuntimeConfigInitializer:
    def __init__(self, *, flows_profile_template: Path) -> None:
        self.flows_profile_template = flows_profile_template

    def initialize(self, *, initialize_database_config: bool) -> None:
        if initialize_database_config:
            _ensure_database_config()
        profile_path = Path.home() / ".skiller" / "settings" / "agent.flows.json"
        if profile_path.exists():
            return
        template = self.flows_profile_template.read_text(encoding="utf-8")
        _write_atomic(profile_path, template, replace=False)


def _ensure_database_config() -> None:
    env_file = load_development_env()
    if "SKILLER_DB_PATH" in os.environ or "SKILLER_DB_PATH" in env_file:
        return
    config_path, _ = resolve_json_config_path(
        env_name="SKILLER_RUNTIME_CONFIG_FILE",
        env_file=env_file,
        default_path=Path.home() / ".skiller" / "settings" / "config.json",
    )
    config_exists = config_path.exists()
    config = load_config(env_file)
    runtime = config.setdefault("runtime", {})
    if not isinstance(runtime, dict):
        raise RuntimeError("Runtime config must contain an object")
    if "db_path" in runtime:
        return

    runtime["db_path"] = "~/.skiller/runtime/global.db"
    _write_atomic(config_path, json.dumps(config, indent=2) + "\n", replace=config_exists)


def _write_atomic(path: Path, content: str, *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        if replace:
            os.replace(temporary_path, path)
            return
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            pass
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
