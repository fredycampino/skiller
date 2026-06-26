from pydantic import BaseModel, ConfigDict, Field

DEFAULT_AGENT_LOOP_MAX_TURNS = 30
DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS = 10
DEFAULT_AGENT_CONTEXT_COMPACTION_ENABLED = False
DEFAULT_AGENT_CONTEXT_COMPACTION_MAX_TOTAL_TOKENS_RATIO = 0.8
DEFAULT_AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED = True
DEFAULT_AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS = 600
DEFAULT_AGENT_EVENT_OUTPUT_MAX_JSON_CHARS = 4000
DEFAULT_AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS = 20


class LLMProviderModelConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    context_window_tokens: int = Field(gt=0)


class LLMProviderConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    models: tuple[LLMProviderModelConfigModel, ...] | None = None
    timeout_seconds: float = Field(gt=0)
    window_width_tokens: int = Field(gt=0)
    api_key: str | None = None
    api_key_env: str | None = None
    api_key_file: str | None = None
    base_url: str | None = None
    credentials_file: str | None = None
    profile: str | None = None


class LLMConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_provider: str
    window_width_tokens: int | None = Field(default=None, gt=0)


class LoopConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_turns: int = Field(default=DEFAULT_AGENT_LOOP_MAX_TURNS, gt=0)
    max_tool_calls: int = Field(default=DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS, gt=0)


class CompactionConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = DEFAULT_AGENT_CONTEXT_COMPACTION_ENABLED
    max_total_tokens_ratio: float = Field(
        default=DEFAULT_AGENT_CONTEXT_COMPACTION_MAX_TOTAL_TOKENS_RATIO,
        gt=0,
        le=1,
    )


class ContextConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compaction: CompactionConfigModel = Field(default_factory=CompactionConfigModel)


class EventOutputTruncateConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = DEFAULT_AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED
    max_text_chars: int = Field(default=DEFAULT_AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS, gt=0)
    max_json_chars: int = Field(default=DEFAULT_AGENT_EVENT_OUTPUT_MAX_JSON_CHARS, gt=0)
    max_array_items: int = Field(default=DEFAULT_AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS, gt=0)


class EventOutputConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    truncate: EventOutputTruncateConfigModel = Field(
        default_factory=EventOutputTruncateConfigModel,
    )


class AgentConfigModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    llm: LLMConfigModel
    providers: dict[str, LLMProviderConfigModel]
    loop: LoopConfigModel = Field(default_factory=LoopConfigModel)
    context: ContextConfigModel = Field(default_factory=ContextConfigModel)
    event_output: EventOutputConfigModel = Field(
        default_factory=EventOutputConfigModel,
    )
    tools: dict[str, dict[str, object]] = Field(default_factory=dict)
