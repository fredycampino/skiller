from __future__ import annotations

import json

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.pretty import Pretty
from rich.text import Text

from skiller.interfaces.tui.screen.theme import DEFAULT_TUI_THEME
from skiller.interfaces.tui.viewmodel.console_screen_state import (
    DispatchErrorItem,
    InfoItem,
    RunAckItem,
    RunOutputItem,
    RunStatusItem,
    RunStepItem,
    TranscriptItem,
    UserInputItem,
)

_SIMPLE_OUTPUT_STEP_TYPES = {
    "notify",
    "llm_prompt",
    "wait_input",
    "wait_webhook",
    "wait_channel",
    "switch",
    "when",
    "send",
}

_STRUCTURED_OUTPUT_STEP_TYPES = {
    "shell",
}


def render_transcript(
    *,
    items: list[TranscriptItem],
    prompt_placeholder: str = DEFAULT_TUI_THEME.prompt_placeholder,
) -> list[RenderableType]:
    if not items:
        return [
            Text(
                prompt_placeholder,
                style=DEFAULT_TUI_THEME.rich_style(DEFAULT_TUI_THEME.color_text_muted),
            )
        ]

    renderables: list[RenderableType] = []
    for index, item in enumerate(items):
        renderables.append(render_transcript_item(item))
        if _needs_separator(item, items, index):
            renderables.append(Text(""))
    return renderables


def render_transcript_item(item: TranscriptItem) -> RenderableType:
    if isinstance(item, UserInputItem):
        return Text(item.text)
    if isinstance(item, InfoItem):
        return Text(item.text)
    if isinstance(item, DispatchErrorItem):
        error_style = DEFAULT_TUI_THEME.rich_style(DEFAULT_TUI_THEME.color_text_error)
        return Group(
            Text("error:", style=error_style),
            Padding(Text(_strip_error_prefix(item.message), style=error_style), (0, 0, 0, 2)),
        )
    if isinstance(item, RunAckItem):
        return Group(
            Text(f"\u21b3 run({item.skill})"),
            Text(f"   created {item.run_id}"),
        )
    if isinstance(item, RunStepItem):
        return Text(f"   [{item.step_type}] {item.step_id}")
    if isinstance(item, RunOutputItem):
        return _render_run_output(step_type=item.step_type, output=item.output)
    if isinstance(item, RunStatusItem):
        if item.status == "error":
            error_style = DEFAULT_TUI_THEME.rich_style(DEFAULT_TUI_THEME.color_text_error)
            if item.message:
                return Group(
                    Text("  error:", style=error_style),
                    Padding(Text(item.message, style=error_style), (0, 0, 0, 3)),
                )
            return Text("  error:", style=error_style)
        return Text(f"  {item.status}")
    return Text("")


def _render_run_output(*, step_type: str, output: str) -> RenderableType:
    normalized = output.strip()
    if not normalized:
        return Text("")

    parsed = _try_parse_json_output(normalized)
    normalized_step_type = step_type.strip().lower()
    if normalized_step_type in _SIMPLE_OUTPUT_STEP_TYPES:
        rendered_simple = _render_simple_output(normalized, parsed)
        if rendered_simple:
            return Text(f"    {rendered_simple}")
        return Text(f"    {normalized}")

    if normalized_step_type in _STRUCTURED_OUTPUT_STEP_TYPES:
        return _render_structured_output(parsed, normalized)

    if parsed is None:
        return Text(f"    {normalized}")
    return _render_structured_output(parsed, normalized)


def _render_simple_output(normalized: str, parsed: object | None) -> str:
    if parsed is None:
        return normalized
    if isinstance(parsed, dict):
        text = parsed.get("text")
        if isinstance(text, str):
            stripped = text.strip()
            if stripped:
                return stripped
    return normalized


def _render_structured_output(parsed: object | None, normalized: str) -> RenderableType:
    if parsed is None:
        return Text(f"    {normalized}")

    render_value = parsed
    if isinstance(parsed, dict) and "value" in parsed:
        render_value = parsed["value"]

    return Padding(
        Pretty(render_value, indent_guides=False, expand_all=True),
        (0, 0, 0, 4),
    )


def _needs_separator(item: TranscriptItem, items: list[TranscriptItem], index: int) -> bool:
    if index >= len(items) - 1:
        return False
    return isinstance(item, UserInputItem)


def _try_parse_json_output(output: str) -> object | None:
    if not output.startswith(("{", "[")):
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def _strip_error_prefix(message: str) -> str:
    normalized = message.strip()
    if normalized.lower().startswith("error:"):
        return normalized[6:].strip()
    return normalized
