from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str = "./runtime.db"
    agent_config_path: str = "~/.skiller/settings/agent.json"
    log_level: str = "INFO"
    webhooks_host: str = "127.0.0.1"
    webhooks_port: int = 8001
    whatsapp_bridge_host: str = "127.0.0.1"
    whatsapp_bridge_port: int = 8002
    whatsapp_bridge_send_timeout_seconds: float = 10.0
    agent_shell_allowlist_enabled: bool = False
    agent_shell_allowlist_workspace: str = ""
    agent_shell_allowlist_allow_env_prefix: bool = True
    agent_shell_allowlist_allowed_commands: tuple[str, ...] = ()
    agent_shell_sandbox_enabled: bool = False
    agent_event_output_truncate_enabled: bool = True
    agent_event_output_max_text_chars: int = 600
    agent_event_output_max_json_chars: int = 4000
    agent_event_output_max_array_items: int = 20
