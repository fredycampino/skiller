from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: str = field(default_factory=lambda: str(Path.home() / ".skiller/runtime/global.db"))
    log_level: str = "INFO"
    webhooks_host: str = "127.0.0.1"
    webhooks_port: int = 8001
