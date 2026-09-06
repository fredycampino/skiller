from pydantic import BaseModel, ConfigDict, Field, field_validator


class RuntimeConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    db_path: str = "./runtime.db"
    log_level: str = "INFO"

    @field_validator("db_path", "log_level")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Runtime config fields must not be empty")
        return normalized


class WebhooksConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str = "127.0.0.1"
    port: int = Field(default=8001, gt=0, le=65535)

    @field_validator("host")
    @classmethod
    def normalize_host(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Webhook host must not be empty")
        return normalized


class SkillerConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(default=1, ge=1)
    runtime: RuntimeConfigModel = Field(default_factory=RuntimeConfigModel)
    webhooks: WebhooksConfigModel = Field(default_factory=WebhooksConfigModel)
    flow_paths: tuple[str, ...] = ()

    @field_validator("flow_paths")
    @classmethod
    def normalize_flow_paths(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        normalized_paths = tuple(path.strip() for path in paths)
        if any(not path for path in normalized_paths):
            raise ValueError("Flow paths must not be empty")
        return normalized_paths
