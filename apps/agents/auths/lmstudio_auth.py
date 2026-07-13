#!/usr/bin/env python3
"""LM Studio auth helper for Skiller agent configuration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CONFIG_FILE = Path(
    os.environ.get(
        "AGENT_AGENT_CONFIG_FILE",
        Path.home() / ".skiller" / "settings" / "agent.json",
    )
).expanduser()


def api_key_file() -> Path:
    return Path.home() / ".skiller" / "secrets" / "lmstudio_api_key"


def configured_state() -> dict:
    """Return current LM Studio configuration state."""
    state: dict = {
        "configured": False,
        "base_url": None,
        "api_key_exists": False,
        "models": [],
    }

    if not CONFIG_FILE.exists():
        return state

    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return state

    provider = config.get("providers", {}).get("lmstudio", {})
    if not provider:
        return state

    state["configured"] = True
    state["base_url"] = provider.get("base_url")
    state["models"] = [
        {"model": m.get("model"), "context_window_tokens": m.get("context_window_tokens")}
        for m in provider.get("models", [])
    ]

    secret_file = api_key_file()
    content = secret_file.read_text(encoding="utf-8").strip()
    state["api_key_exists"] = secret_file.exists() and bool(content)

    return state


def write_config(base_url: str) -> None:
    """Write LM Studio base_url to agent.json, clearing models."""
    if not base_url or not base_url.strip():
        raise ValueError("base_url is required")

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}
    else:
        config = {}

    providers = config.setdefault("providers", {})
    providers["lmstudio"] = {
        "base_url": base_url.strip(),
        "api_key_file": str(api_key_file()),
        "model": None,
        "models": [],
    }

    CONFIG_FILE.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_api_key(key: str) -> None:
    """Write LM Studio API key to secret file."""
    if not key or not key.strip():
        raise ValueError("API key is required")

    secret_file = api_key_file()
    secret_file.parent.mkdir(parents=True, exist_ok=True)

    old_umask = os.umask(0o077)
    try:
        secret_file.write_text(key.strip() + "\n", encoding="utf-8")
    finally:
        os.umask(old_umask)


def get_lmstudio_config() -> dict:
    """Return the raw lmstudio config section from agent.json."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    return config.get("providers", {}).get("lmstudio", {})


def format_state(state: dict, lmstudio_status: dict) -> str:
    """Format state for user display."""
    configured = state.get("configured", False)
    base_url = state.get("base_url")
    api_key_exists = state.get("api_key_exists", False)
    models = state.get("models", [])
    server_models = lmstudio_status.get("data", [])

    lines = []
    lines.append(f"**Configurado:** {'Sí' if configured else 'No'}")
    if configured:
        lines.append(f"**Server:** {base_url or 'localhost:1234'}")
        lines.append(f"**API Token:** {'Configurado' if api_key_exists else 'No'}")

    if server_models:
        lines.append("**Models (desde servidor):**")
        for m in server_models[:5]:
            mid = m.get("id", "unknown")
            ctx = m.get("context_window", 0) or 0
            lines.append(f"  • `{mid}` ({ctx:,} tokens)")
        if len(server_models) > 5:
            lines.append(f"  ... y {len(server_models) - 5} más")
    elif models:
        lines.append("**Models (guardados):**")
        for m in models[:5]:
            mid = m.get("model", "unknown")
            ctx = m.get("context_window_tokens", 0) or 0
            lines.append(f"  • `{mid}` ({ctx:,} tokens)")

    return "\n".join(lines)


def format_menu() -> str:
    """Format full menu with raw JSON config for user display."""
    lmstudio_config = get_lmstudio_config()

    lines = []
    lines.append("We found a global configuration on `~/.skiller/settings/agent.json`\n")

    if lmstudio_config:
        lines.append("```json")
        lines.append(json.dumps({"lmstudio": lmstudio_config}, indent=2))
        lines.append("```")
    else:
        lines.append("```json")
        lines.append("{}")
        lines.append("```")

    lines.append("\n## Choose an option (1-6)\n")
    lines.append("1. Add API token")
    lines.append("2. Url Server")
    lines.append("3. Check connection")
    lines.append("4. Update models list")
    lines.append("5. Status")
    lines.append("6. Exit")

    return "\n".join(lines)


def check_connection() -> dict:
    """Check connection to LM Studio server. Returns dict with result."""
    config = get_lmstudio_config()
    base_url = config.get("base_url", "http://localhost:1234")
    api_key = None

    secret_file = api_key_file()
    if secret_file.exists():
        api_key = secret_file.read_text(encoding="utf-8").strip()

    import urllib.request

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        f"{base_url}/v1/models",
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            return {
                "success": True,
                "base_url": base_url,
                "models_count": len(models),
            }
    except Exception as exc:
        return {
            "success": False,
            "base_url": base_url,
            "error": str(exc),
        }


def format_check_connection(result: dict) -> str:
    """Format check connection result for user display."""
    if result.get("success"):
        return (
            f"Connected to {result['base_url']}\n"
            f"Found {result['models_count']} models"
        )
    else:
        return f"Connection failed: {result.get('error', 'unknown error')}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LM Studio credential helper for Skiller onboarding."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("api-key-file", help="Print the resolved API key file path.")
    subparsers.add_parser("configured-state", help="Print LM Studio current configuration as JSON.")

    p_format = subparsers.add_parser("format-state", help="Format state for user display.")
    p_format.add_argument("state", help="JSON state from configured-state.")
    p_format.add_argument("lmstudio_status", help="JSON from /v1/models endpoint.")

    p_write_config = subparsers.add_parser("write-config", help="Write base_url to config.")
    p_write_config.add_argument("base_url", help="The LM Studio server base URL.")

    p_add_key = subparsers.add_parser("add-api-key", help="Write API key to secret file.")
    p_add_key.add_argument("api_key", help="The API key to store.")

    subparsers.add_parser("format-menu", help="Format full menu with raw JSON config.")

    subparsers.add_parser(
        "check-connection",
        help="Check connection to LM Studio server.",
    )

    args = parser.parse_args()

    try:
        if args.command == "api-key-file":
            print(api_key_file())
        elif args.command == "configured-state":
            print(json.dumps(configured_state()))
        elif args.command == "format-state":
            state = json.loads(args.state)
            lmstudio_status = json.loads(args.lmstudio_status)
            print(format_state(state, lmstudio_status))
        elif args.command == "write-config":
            write_config(args.base_url)
            print("saved")
        elif args.command == "add-api-key":
            add_api_key(args.api_key)
            print("saved")
        elif args.command == "format-menu":
            print(format_menu())
        elif args.command == "check-connection":
            print(format_check_connection(check_connection()))
        return 0
    except Exception as exc:
        print(f"{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
