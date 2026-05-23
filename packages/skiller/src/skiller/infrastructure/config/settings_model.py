from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str = "./runtime.db"
    log_level: str = "INFO"
    webhooks_host: str = "127.0.0.1"
    webhooks_port: int = 8001
    whatsapp_bridge_host: str = "127.0.0.1"
    whatsapp_bridge_port: int = 8002
    whatsapp_bridge_send_timeout_seconds: float = 10.0
