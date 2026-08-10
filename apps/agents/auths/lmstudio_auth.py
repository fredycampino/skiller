#!/usr/bin/env python3
"""LM Studio auth helper for Skiller agent configuration."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_FILE = Path(
    os.environ.get(
        "AGENT_AGENT_CONFIG_FILE",
        Path.home() / ".skiller" / "settings" / "agent.json",
    )
).expanduser()


def api_key_file() -> Path:
    return Path.home() / ".skiller" / "secrets" / "lmstudio_api_key"


def normalize_lmstudio_base_url(base_url: str) -> str:
    """Return LM Studio OpenAI-compatible base URL."""
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def print_config() -> dict:
    """Return the raw LM Studio provider config from agent.json."""
    return get_lmstudio_config()


def configured_state() -> dict:
    """Return current LM Studio configuration state."""
    provider = print_config()
    state: dict = {
        "configured": bool(provider),
        "base_url": provider.get("base_url") if provider else None,
        "api_key_exists": False,
        "models": [],
    }

    if not provider:
        return state

    state["models"] = [
        {"model": m.get("model"), "context_window_tokens": m.get("context_window_tokens")}
        for m in provider.get("models", [])
    ]

    api_key_path = provider.get("api_key_file") or str(api_key_file())
    secret_file = Path(str(api_key_path)).expanduser()
    if secret_file.exists():
        content = secret_file.read_text(encoding="utf-8").strip()
        state["api_key_exists"] = bool(content)

    return state

def ensure_lmstudio_llm_fallback(config: dict) -> None:
    """Ensure empty configs use LM Studio as default LLM provider."""
    llm = config.setdefault("llm", {})
    if not llm:
        llm["default_provider"] = "lmstudio"


def write_config(base_url: str = "http://localhost:1234/v1") -> None:
    """Write the default LM Studio provider config to agent.json."""
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

    ensure_lmstudio_llm_fallback(config)
    context = config.setdefault("context", {})
    context.setdefault("window_width_tokens", 100000)
    provider = default_lmstudio_provider()
    provider["base_url"] = normalize_lmstudio_base_url(base_url)
    providers = config.setdefault("providers", {})
    providers["lmstudio"] = provider

    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

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
    """Format LM Studio provider menu for user display."""
    return "\n".join(
        [
            "# LM Studio provider",
            "",
            "1. Provider status",
            "2. Check connection",
            "3. Exit",
        ]
    )


def default_lmstudio_provider() -> dict:
    """Return the default LM Studio provider config."""
    return {
        "base_url": "http://localhost:1234/v1",
        "api_key_file": str(api_key_file()),
        "model": None,
        "models": [],
        "timeout_seconds": 120,
    }


def ensure_lmstudio_provider() -> dict:
    """Return LM Studio provider config, creating it when missing."""
    provider = print_config()
    if provider:
        return provider
    write_config()
    return print_config()

def check_connection() -> dict:
    """Check connection to LM Studio server. Returns dict with result."""
    provider = print_config() or default_lmstudio_provider()
    return check_connection_for_provider(provider)

def loaded_lmstudio_models() -> list[dict]:
    """Return models currently loaded in LM Studio memory."""
    try:
        completed = subprocess.run(
            ["lms", "ps", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if completed.returncode != 0 or not completed.stdout.strip():
        return []

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []

    return data if isinstance(data, list) else []


def available_lmstudio_models(base_url: str = "http://localhost:1234/v1") -> dict:
    """Return downloaded LM Studio models and mark models loaded in memory."""
    normalized_base_url = normalize_lmstudio_base_url(base_url)
    req = urllib.request.Request(f"{normalized_base_url}/models")
    with urllib.request.urlopen(req, timeout=5) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    downloaded = payload.get("data", [])
    loaded_models = {
        item.get("identifier"): item
        for item in loaded_lmstudio_models()
        if isinstance(item, dict) and item.get("identifier")
    }

    models = []
    selected_model = None
    for item in downloaded:
        model_id = item.get("id") if isinstance(item, dict) else None
        if not model_id:
            continue

        loaded = loaded_models.get(model_id)
        context_window_tokens = 0
        if loaded:
            context_window_tokens = loaded.get("contextLength") or 0
            selected_model = selected_model or model_id

        models.append(
            {
                "model": model_id,
                "context_window_tokens": context_window_tokens,
                "loaded": bool(loaded),
            }
        )

    if selected_model is None and models:
        selected_model = models[0]["model"]

    return {"model": selected_model, "models": models}


def check_connection_for_provider(config: dict) -> dict:
    """Check connection to LM Studio using the given provider config."""
    base_url = normalize_lmstudio_base_url(config.get("base_url", "http://localhost:1234/v1"))
    api_key = None

    api_key_path = config.get("api_key_file") or str(api_key_file())
    secret_file = Path(str(api_key_path)).expanduser()
    if secret_file.exists():
        api_key = secret_file.read_text(encoding="utf-8").strip()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    endpoint = f"{base_url}/models"
    req = urllib.request.Request(endpoint, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            return {
                "success": True,
                "base_url": base_url,
                "endpoint": endpoint,
                "models_count": len(models),
                "models": models,
                "loaded_models": loaded_lmstudio_models(),
            }
    except urllib.error.HTTPError as exc:
        return {
            "success": False,
            "base_url": base_url,
            "endpoint": endpoint,
            "error_type": "auth" if exc.code in (401, 403) else "http",
            "status_code": exc.code,
            "error": str(exc),
        }
    except TimeoutError as exc:
        return {
            "success": False,
            "base_url": base_url,
            "endpoint": endpoint,
            "error_type": "timeout",
            "error": str(exc),
        }
    except urllib.error.URLError as exc:
        reason = exc.reason
        error_type = "timeout" if isinstance(reason, socket.timeout) else "connection"
        return {
            "success": False,
            "base_url": base_url,
            "endpoint": endpoint,
            "error_type": error_type,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "success": False,
            "base_url": base_url,
            "endpoint": endpoint,
            "error_type": "unknown",
            "error": str(exc),
        }



def add_models(available_models: dict) -> None:
    """Update LM Studio models from available-models output."""
    incoming_models = available_models.get("models", [])
    if not isinstance(incoming_models, list) or not incoming_models:
        raise ValueError("models list is required")

    normalized_models = []
    seen = set()
    for item in incoming_models:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model") or "").strip()
        if not model_id or model_id in seen:
            continue
        context_window_tokens = item.get("context_window_tokens") or 0
        if context_window_tokens == 0:
            context_window_tokens = 50000
        normalized_models.append(
            {
                "model": model_id,
                "context_window_tokens": context_window_tokens,
            }
        )
        seen.add(model_id)

    if not normalized_models:
        raise ValueError("at least one model is required")

    if not print_config():
        write_config()

    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}
    else:
        config = {}

    providers = config.setdefault("providers", {})
    provider = providers.setdefault("lmstudio", default_lmstudio_provider())
    current_model = provider.get("model")
    provider["models"] = normalized_models

    model_ids = {item["model"] for item in normalized_models}
    suggested_model = available_models.get("model")
    if suggested_model not in model_ids:
        suggested_model = normalized_models[0]["model"]

    if current_model is None or current_model not in model_ids:
        provider["model"] = suggested_model

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

def provider_status() -> str:
    """Format provider config and connection status."""
    if not print_config():
        write_config()
    provider = print_config()
    connection = check_connection_for_provider(provider)
    lines = [
        "```json",
        json.dumps({"lmstudio": provider}, indent=2, sort_keys=True),
        "```",
        "",
    ]
    if connection.get("success"):
        lines.append(f"Connection: OK ({connection['base_url']})")
        lines.append(f"Server models: {connection['models_count']}")
    else:
        lines.append(f"Connection: Failed ({connection['base_url']})")
        lines.append(f"Error: {connection.get('error', 'unknown error')}")
    return "\n".join(lines)

def format_check_connection(result: dict) -> str:
    """Format check connection result for user display."""
    endpoint = result.get("endpoint") or (
        f"{normalize_lmstudio_base_url(result.get('base_url', 'http://localhost:1234/v1'))}/models"
    )
    lines = [
        "## LMStudio",
        "- Status: found and ready to use",
        "",
        "## API endpoint connection",
        f"- Endpoint: {endpoint}",
    ]

    if result.get("success"):
        lines.append(f"- Result: Connection OK. Retrieved {result['models_count']} models.")
        models = result.get("models", [])
        loaded_models = {
            item.get("identifier"): item
            for item in result.get("loaded_models", [])
            if isinstance(item, dict) and item.get("identifier")
        }
        if models:
            lines.extend(["", "## Downloaded Models"])
            for model in models:
                model_id = model.get("id") if isinstance(model, dict) else str(model)
                lines.append(f"- {model_id or 'unknown'}")

        for model_id, loaded_model in loaded_models.items():
            context_length = loaded_model.get("contextLength") or 0
            max_context_length = loaded_model.get("maxContextLength") or 0
            lines.extend(["", f"## Loaded model {model_id}"])
            if context_length >= 50000:
                lines.append("- Context length OK")
            else:
                lines.append(
                    "- Context length too small, it requires 50K minimum. "
                    "Adjust context length in LM Studio."
                )
            lines.append(f"- Context length limited to {context_length:,} tokens")
            lines.append(f"- Model supports up to {max_context_length:,} tokens")
        return "\n".join(lines)

    error_type = result.get("error_type")
    if error_type == "connection":
        message = (
            "Connection FAIL, could not connect. The server seems to be off or"
            " not listening at that URL."
        )
    elif error_type == "timeout":
        message = "Connection FAIL. The server took too long to respond"
    elif error_type == "auth":
        message = (
            "Connection Error, the server responded but rejected authentication."
            " Check the configured API key."
        )
    elif error_type == "http":
        message = (
            f"Connection Error, the server responded with HTTP error {result.get('status_code')}."
        )
    else:
        message = f"Could not verify the connection: {result.get('error', 'unknown error')}."

    lines.append(f"- Result: {message}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LM Studio credential helper for Skiller onboarding."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("api-key-file", help="Print the resolved API key file path.")
    subparsers.add_parser("print-config", help="Print LM Studio provider config as JSON.")

    p_format = subparsers.add_parser("format-state", help="Format state for user display.")
    p_format.add_argument("state", help="JSON state to format.")
    p_format.add_argument("lmstudio_status", help="JSON from /v1/models endpoint.")

    p_write_config = subparsers.add_parser("write-config", help="Write base_url to config.")
    p_write_config.add_argument(
        "base_url",
        nargs="?",
        default="http://localhost:1234/v1",
        help="The LM Studio OpenAI-compatible base URL.",
    )

    p_add_key = subparsers.add_parser("add-api-key", help="Write API key to secret file.")
    p_add_key.add_argument("api_key", help="The API key to store.")

    p_add_models = subparsers.add_parser(
        "add-models",
        help="Update models from available-models JSON.",
    )
    p_add_models.add_argument("models_json", help="JSON returned by available-models.")

    subparsers.add_parser("format-menu", help="Format the LM Studio provider menu.")

    p_available_models = subparsers.add_parser(
        "available-models",
        help="Print downloaded models and mark models loaded in memory as JSON.",
    )
    p_available_models.add_argument(
        "base_url",
        nargs="?",
        default="http://localhost:1234/v1",
        help="The LM Studio OpenAI-compatible base URL.",
    )

    subparsers.add_parser(
        "check-connection",
        help="Check connection to LM Studio server.",
    )
    subparsers.add_parser("provider-status", help="Print LM Studio provider status.")

    args = parser.parse_args()

    try:
        if args.command == "api-key-file":
            print(api_key_file())
        elif args.command == "print-config":
            print(json.dumps(print_config(), indent=2, sort_keys=True))
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
        elif args.command == "add-models":
            add_models(json.loads(args.models_json))
            print("saved")
        elif args.command == "format-menu":
            print(format_menu())
        elif args.command == "available-models":
            print(json.dumps(available_lmstudio_models(args.base_url), indent=2, sort_keys=True))
        elif args.command == "check-connection":
            print(format_check_connection(check_connection()))
        elif args.command == "provider-status":
            print(provider_status())
        return 0
    except Exception as exc:
        print(f"{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
