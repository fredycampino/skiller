from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    db_path: str
    log_level: str


@dataclass(frozen=True)
class WebhooksConfig:
    host: str
    port: int


@dataclass(frozen=True)
class SkillerConfig:
    version: int
    runtime: RuntimeConfig
    webhooks: WebhooksConfig
    flow_paths: tuple[Path, ...]
