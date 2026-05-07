from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str = "./runtime.db"
    llm_provider: str = "null"
    fake_llm_response_json: str = (
        '{"summary":"fake summary","severity":"low","next_action":"retry"}'
    )
    fake_llm_model: str = "fake-llm"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.io/v1"
    minimax_model: str = "MiniMax-M2.5"
    minimax_timeout_seconds: float = 30.0
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
    agent_event_output_pii_enabled: bool = True
    agent_event_output_secrets_enabled: bool = True
    agent_event_output_max_text_chars: int = 600
    agent_event_output_max_json_chars: int = 4000
    agent_event_output_max_array_items: int = 20
    agent_loop_max_turns: int = 10
    agent_loop_max_tool_calls: int = 5
