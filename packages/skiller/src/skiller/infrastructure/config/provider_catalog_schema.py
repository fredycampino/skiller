from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from skiller.domain.agent.llm.model import LLMToolChoiceMode
from skiller.domain.agent.llm.provider_catalog import LLMAdapterType


class LLMModelConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(min_length=1)
    context_window_tokens: int = Field(gt=0)

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM model must not be empty")
        return normalized


class LLMProviderConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    adapter: LLMAdapterType | None = None
    enabled: bool | None = None
    timeout_seconds: float | None = Field(default=None, gt=0)
    models: tuple[LLMModelConfigModel, ...] | None = Field(
        default=None,
        min_length=1,
    )

    base_url: str | None = Field(default=None, min_length=1)
    temperature: float | None = Field(default=None, ge=0)
    top_p: float | None = Field(default=None, gt=0, le=1)
    max_output_tokens: int | None = Field(default=None, gt=0)
    parallel_tool_calls: bool | None = None
    tool_choice: LLMToolChoiceMode | None = None
    api_key: str | None = Field(default=None, min_length=1)
    api_key_env: str | None = Field(default=None, min_length=1)
    api_key_file: str | None = Field(default=None, min_length=1)
    options: dict[str, object] | None = None

    profile: str | None = Field(default=None, min_length=1)

    credentials_file: str | None = Field(default=None, min_length=1)

    @field_validator(
        "name",
        "base_url",
        "api_key",
        "api_key_env",
        "api_key_file",
        "profile",
        "credentials_file",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("LLM provider text fields must not be empty")
        return normalized

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        null_fields = sorted(key for key, item in value.items() if item is None)
        if null_fields:
            fields = ", ".join(null_fields)
            raise ValueError(f"LLM provider fields must not be null: {fields}")
        return value

    @model_validator(mode="after")
    def validate_api_key_source(self) -> "LLMProviderConfigModel":
        sources = (self.api_key, self.api_key_env, self.api_key_file)
        if sum(source is not None for source in sources) > 1:
            raise ValueError("OpenAI LLM provider accepts only one api_key source")
        return self


class LLMProviderCatalogSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    providers: dict[str, dict[str, object]]
