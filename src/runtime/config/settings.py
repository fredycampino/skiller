from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("AGENT_DB_PATH", "./runtime.db")
    log_level: str = os.getenv("AGENT_LOG_LEVEL", "INFO")
    webhook_secret: str = os.getenv("AGENT_WEBHOOK_SECRET", "")


def get_settings() -> Settings:
    return Settings()
