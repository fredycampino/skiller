from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str = "./runtime.db"
    log_level: str = "INFO"
    webhooks_host: str = "127.0.0.1"
    webhooks_port: int = 8001
