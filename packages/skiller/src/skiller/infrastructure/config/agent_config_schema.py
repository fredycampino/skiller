from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_AGENT_LOOP_MAX_TURNS = 30
DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS = 10
DEFAULT_AGENT_CONTEXT_COMPACTION_TRIGGER_RATIO = 0.8
DEFAULT_AGENT_CONTEXT_COMPACTION_TARGET_RATIO = 0.5
DEFAULT_AGENT_CONTEXT_COMPACTION_KEEP_LAST_BLOCKS = 5
DEFAULT_AGENT_EVENT_OUTPUT_TRUNCATE_ENABLED = True
DEFAULT_AGENT_EVENT_OUTPUT_MAX_TEXT_CHARS = 600
DEFAULT_AGENT_EVENT_OUTPUT_MAX_JSON_CHARS = 4000
DEFAULT_AGENT_EVENT_OUTPUT_MAX_ARRAY_ITEMS = 20


class LLMConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)

    @field_validator("provider", "model")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Agent LLM selection fields must not be empty")
        return normalized


class DebugConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_request: bool = False
    log_streaming: bool = False
    log_request_file: str | None = None
    log_override_file: bool = True


class LoopConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_turns: int = Field(default=DEFAULT_AGENT_LOOP_MAX_TURNS, gt=0)
    max_tool_calls: int = Field(default=DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS, gt=0)


class CompactionConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compaction_trigger_ratio: float = Field(
        default=DEFAULT_AGENT_CONTEXT_COMPACTION_TRIGGER_RATIO,
        gt=0,
        le=1,
    )
    compaction_target_ratio: float = Field(
        default=DEFAULT_AGENT_CONTEXT_COMPACTION_TARGET_RATIO,
        gt=0,
        le=1,
    )
    keep_last_blocks: int = Field(
        default=DEFAULT_AGENT_CONTEXT_COMPACTION_KEEP_LAST_BLOCKS,
        gt=0,
        le=100,
    )

    @model_validator(mode="after")
    def validate_compaction_ratios(self) -> Self:
        if self.compaction_target_ratio >= self.compaction_trigger_ratio:
            raise ValueError("compaction_target_ratio must be lower than compaction_trigger_ratio")
        return self


class ContextConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_width_tokens: int | None = Field(default=None, gt=0)
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
    model_config = ConfigDict(extra="forbid")

    llm: LLMConfigModel
    debug: DebugConfigModel = Field(default_factory=DebugConfigModel)
    loop: LoopConfigModel = Field(default_factory=LoopConfigModel)
    context: ContextConfigModel = Field(default_factory=ContextConfigModel)
    event_output: EventOutputConfigModel = Field(
        default_factory=EventOutputConfigModel,
    )
    tools: dict[str, dict[str, object]] = Field(default_factory=dict)
