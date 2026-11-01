import json
import os
from pathlib import Path


def load_development_env() -> dict[str, str]:
    env_path = Path.cwd() / ".env.development"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    lines = env_path.read_text(encoding="utf-8").splitlines()
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in {"SKILLER_DB_PATH", "SKILLER_RUNTIME_CONFIG_FILE"}:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_config(env_file: dict[str, str]) -> dict[str, object]:
    config_path, explicit = resolve_json_config_path(
        env_name="SKILLER_RUNTIME_CONFIG_FILE",
        env_file=env_file,
        default_path=Path.home() / ".skiller" / "settings" / "config.json",
    )
    return _load_json_config_file(
        config_path=config_path,
        env_name="SKILLER_RUNTIME_CONFIG_FILE",
        explicit=explicit,
    )


def resolve_json_config_path(
    *,
    env_name: str,
    env_file: dict[str, str],
    default_path: Path,
) -> tuple[Path, bool]:
    explicit_path = os.environ.get(env_name, "").strip()
    if not explicit_path:
        explicit_path = env_file.get(env_name, "").strip()
    config_path = Path(explicit_path).expanduser() if explicit_path else default_path
    return config_path, bool(explicit_path)


def _load_json_config_file(
    *,
    config_path: Path,
    env_name: str,
    explicit: bool,
) -> dict[str, object]:
    if not config_path.exists():
        if explicit:
            raise RuntimeError(f"{env_name} does not exist: {config_path}")
        return {}

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        display_path = _display_path(config_path)
        raise RuntimeError(
            f"Invalid JSON config file: {display_path} (line {exc.lineno}, column {exc.colno})"
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


