from __future__ import annotations

import json
import re
from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.padding import Padding
from rich.pretty import Pretty
from rich.segment import Segment, Segments
from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    DispatchErrorItem,
    InfoItem,
    OutputFormat,
    RunAckItem,
    RunOutputItem,
    RunResumeItem,
    RunStatusItem,
    RunStepItem,
    TranscriptItem,
    TranscriptMode,
    UserInputItem,
)

_INLINE_CONDITIONAL_STEP_TYPES = {
    "switch",
    "when",
}

_WAIT_STEP_TYPES = {
    "wait_input",
    "wait_webhook",
    "wait_channel",
}

_ROUTE_SELECTED_RE = re.compile(
    r"^\s*Route selected:\s*(?P<target>[^.]+)\.?\s*$",
    re.IGNORECASE,
)
_MARKDOWN_CODE_THEME = "monokai" #default theme, dracula, github-light


def render_transcript(
    *,
    items: list[TranscriptItem],
    mode: TranscriptMode = TranscriptMode.FLOW,
    theme: TuiTheme = DEFAULT_TUI_THEME,
    prompt_placeholder: str | None = None,
) -> list[RenderableType]:
    placeholder = (
        theme.prompt_placeholder
        if prompt_placeholder is None
        else prompt_placeholder
    )
    if not items:
        return [
            Text(
                placeholder,
                style=theme.rich_style(theme.color_text_muted),
            )
        ]

    renderables: list[RenderableType] = []
    active_tool_call_index = _find_active_tool_call_index(items)
    index = 0
    while index < len(items):
        item = items[index]

        if isinstance(item, RunStatusItem) and item.status.strip().lower() == "waiting":
            index += 1
            continue

        if index + 1 < len(items):
            collapsed = _render_inline_conditional_route(
                item=item,
                next_item=items[index + 1],
                theme=theme,
            )
            if collapsed is not None:
                renderables.append(collapsed)
                if _needs_blank_line_after_collapsed_conditional(
                    items=items,
                    next_index=index + 2,
                ):
                    renderables.append(Text(""))
                index += 2
                continue

        if _needs_prefix_separator(items=items, index=index):
            renderables.append(Text(""))
        renderables.append(
            render_transcript_item(
                item,
                mode=mode,
                theme=theme,
                is_active_tool_call=index == active_tool_call_index,
            )
        )
        if _needs_separator(item, items, index):
            renderables.append(Text(""))
        index += 1
    return renderables


def render_transcript_item(
    item: TranscriptItem,
    *,
    mode: TranscriptMode = TranscriptMode.FLOW,
    theme: TuiTheme = DEFAULT_TUI_THEME,
    is_active_tool_call: bool = False,
) -> RenderableType:
    if isinstance(item, UserInputItem):
        return _wrap_prefixed_renderable(
            prefix=_text(
                theme.user_icon,
                style=theme.rich_style(theme.color_text_accent),
            ),
            renderable=_text(
                item.text,
                style=theme.rich_style(theme.color_text_accent),
            ),
            prefix_width=1,
        )
    if isinstance(item, InfoItem):
        return Text(item.text)
    if isinstance(item, DispatchErrorItem):
        error_style = theme.rich_style(theme.color_text_error)
        return Group(
            Text("error:", style=error_style),
            Padding(Text(_strip_error_prefix(item.message), style=error_style), (0, 0, 0, 2)),
        )
    if isinstance(item, RunAckItem):
        return Group(
            Text(f"\u21b3 run({item.skill})"),
            Text(f"   created {item.run_id}"),
        )
    if isinstance(item, RunResumeItem):
        return Text(
            f"\u21b3 resume({item.skill})",
            style=theme.rich_style(theme.color_text_muted),
        )
    if isinstance(item, RunStepItem):
        normalized_step_type = item.step_type.strip().lower()
        if normalized_step_type in _WAIT_STEP_TYPES:
            return Text(
                "   ...",
                style=theme.rich_style(theme.color_text_muted),
            )
        if normalized_step_type == "agent":
            tag_style = _agent_step_tag_style(theme=theme, mode=mode)
            id_style = _agent_step_id_style(theme=theme, mode=mode)
            renderable = Text("[")
            renderable.stylize(tag_style, 0, 1)
            renderable.append(
                item.step_type,
                style=tag_style,
            )
            renderable.append("] ")
            renderable.stylize(tag_style, len(renderable.plain) - 2, len(renderable.plain))
            renderable.append(
                item.step_id,
                style=id_style,
            )
            return renderable
        return Text(f"   [{item.step_type}] {item.step_id}")
    if isinstance(item, AgentToolCallItem):
        tool_style = (
            theme.rich_style(theme.color_text_primary)
            if is_active_tool_call
            else theme.rich_style(theme.color_text_muted)
        )
        return _wrap_prefixed_renderable(
            prefix=_text(
                theme.agent_tool_icon,
                style=tool_style,
            ),
            renderable=_text(
                f"$ {item.command}",
                style=tool_style,
            ),
            prefix_width=1,
        )
    if isinstance(item, AgentToolResultItem):
        return Padding(
            _text(
                item.preview,
                style=theme.rich_style(theme.color_text_muted),
            ),
            (0, 0, 0, 4),
        )
    if isinstance(item, AgentAssistantMessageItem):
        return _wrap_agent_renderable(
            _render_agent_assistant_content(
                item=item,
                theme=theme,
            ),
            theme=theme,
        )
    if isinstance(item, AgentSystemNoticeItem):
        warning_style = theme.rich_style(theme.color_text_warning)
        return _wrap_prefixed_renderable(
            prefix=_text(
                theme.system_warning_icon,
                style=warning_style,
            ),
            renderable=_text(
                item.text,
                style=warning_style,
            ),
            prefix_width=1,
        )
    if isinstance(item, RunOutputItem):
        return _render_run_output(
            theme=theme,
            step_type=item.step_type,
            output=item.output,
            format=item.format,
        )
    if isinstance(item, RunStatusItem):
        if item.status == "error":
            error_style = theme.rich_style(theme.color_text_error)
            if item.message:
                return Group(
                    Text("  error:", style=error_style),
                    Padding(Text(item.message, style=error_style), (0, 0, 0, 3)),
                )
            return Text("  error:", style=error_style)
        return Text(f"  {item.status}")
    return Text("")


def _text(value: str, *, style: str = "") -> Text:
    return Text(
        value,
        style=style,
        overflow="fold",
        no_wrap=False,
    )


def _agent_step_tag_style(*, theme: TuiTheme, mode: TranscriptMode) -> str:
    if mode == TranscriptMode.CHAT:
        base_style = theme.rich_style(theme.color_text_muted)
        return f"{base_style} dim".strip()
    return theme.rich_style(theme.color_text_accent)


def _agent_step_id_style(*, theme: TuiTheme, mode: TranscriptMode) -> str:
    if mode == TranscriptMode.CHAT:
        base_style = theme.rich_style(theme.color_text_muted)
        return f"{base_style} dim".strip()
    return theme.rich_style(theme.color_text_secondary)


def _render_run_output(
    *,
    theme: TuiTheme,
    step_type: str,
    output: str,
    format: OutputFormat,
) -> RenderableType:
    normalized = output.strip()
    if not normalized:
        return Text("")

    parsed = _try_parse_json_output(normalized)
    indent = _output_indent(step_type)
    if format == OutputFormat.SIMPLE:
        rendered_simple = _render_simple_output(normalized, parsed)
        if rendered_simple:
            if step_type.strip().lower() == "agent":
                return _wrap_agent_renderable(
                    Text(rendered_simple),
                    theme=theme,
                )
            return Text(_format_simple_output(rendered_simple, step_type=step_type, theme=theme))
        if step_type.strip().lower() == "agent":
            return _wrap_agent_renderable(
                Text(normalized),
                theme=theme,
            )
        return Text(_format_simple_output(normalized, step_type=step_type, theme=theme))

    if format == OutputFormat.MARKDOWN:
        if step_type.strip().lower() == "agent":
            return _wrap_agent_renderable(
                _render_agent_content(output=normalized, format=format, parsed=parsed),
                theme=theme,
            )
        return _render_markdown_output(
            normalized,
            parsed,
            indent=indent,
            step_type=step_type,
            theme=theme,
        )

    if format == OutputFormat.STRUCTURED:
        return _render_structured_output(parsed, normalized, indent=indent)

    if parsed is None:
        return Text(_format_simple_output(normalized, step_type=step_type, theme=theme))
    return _render_structured_output(parsed, normalized, indent=indent)


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


def _render_structured_output(
    parsed: object | None,
    normalized: str,
    *,
    indent: int,
) -> RenderableType:
    if parsed is None:
        return Text(_indent_block(normalized, spaces=indent))

    render_value = parsed
    if isinstance(parsed, dict) and "value" in parsed:
        render_value = parsed["value"]

    return Padding(
        Pretty(render_value, indent_guides=False, expand_all=True),
        (0, 0, 0, indent),
    )


def _render_markdown_output(
    normalized: str,
    parsed: object | None,
    *,
    indent: int,
    step_type: str,
    theme: TuiTheme,
) -> RenderableType:
    markdown_text = _extract_markdown_text(normalized, parsed)
    if not markdown_text.strip():
        return Text("")
    # Rich code themes come from the installed Pygments/Rich set.
    # Common options available in this env: monokai, github-dark,
    # github-light, dracula, native, fruity, bw.
    return Padding(
        Markdown(markdown_text, code_theme=_MARKDOWN_CODE_THEME),
        (0, 0, 0, indent),
    )


def _render_agent_content(
    *,
    output: str,
    format: OutputFormat,
    parsed: object | None = None,
) -> RenderableType:
    normalized = output.strip()
    if not normalized:
        return Text("")

    resolved_parsed = parsed
    if resolved_parsed is None:
        resolved_parsed = _try_parse_json_output(normalized)

    if format == OutputFormat.MARKDOWN:
        markdown_text = _extract_markdown_text(normalized, resolved_parsed)
        return Markdown(markdown_text, code_theme=_MARKDOWN_CODE_THEME)

    if format == OutputFormat.STRUCTURED:
        return _render_structured_output(resolved_parsed, normalized, indent=0)

    rendered_simple = _render_simple_output(normalized, resolved_parsed)
    return Text(rendered_simple or normalized)


def _extract_markdown_text(normalized: str, parsed: object | None) -> str:
    if isinstance(parsed, dict):
        text = parsed.get("text")
        if isinstance(text, str):
            return text
    return normalized


def _render_agent_assistant_content(
    *,
    item: AgentAssistantMessageItem,
    theme: TuiTheme,
) -> RenderableType:
    renderable = _render_agent_content(
        output=item.text,
        format=item.format,
    )
    if item.message_type.strip().lower() == "final":
        return renderable
    return Styled(
        renderable,
        style=theme.rich_style(theme.color_text_secondary),
    )


def _wrap_agent_renderable(
    renderable: RenderableType,
    *,
    theme: TuiTheme,
) -> Table:
    return _wrap_prefixed_renderable(
        prefix=_text(
            theme.agent_message_icon,
            style=theme.rich_style(theme.color_text_primary),
        ),
        renderable=_TrimLeadingBlankLines(renderable),
        prefix_width=1,
    )


def _wrap_prefixed_renderable(
    *,
    prefix: RenderableType,
    renderable: RenderableType,
    prefix_width: int,
) -> Table:
    grid = Table.grid(padding=(0, 0))
    grid.add_column(width=prefix_width)
    grid.add_column()
    grid.add_row(prefix, Padding(renderable, (0, 0, 0, 1)))
    return grid


@dataclass(frozen=True)
class _TrimLeadingBlankLines:
    renderable: RenderableType

    def __rich_console__(self, console, options):  # noqa: ANN001
        lines = console.render_lines(self.renderable, options, pad=False)
        while lines and _line_is_blank(lines[0]):
            lines.pop(0)
        while lines and _line_is_blank(lines[-1]):
            lines.pop()
        if not lines:
            return

        for index, line in enumerate(lines):
            yield Segments(line)
            if index < len(lines) - 1:
                yield Segment.line()


def _line_is_blank(line: list[Segment]) -> bool:
    return not "".join(segment.text for segment in line).strip()


def _output_indent(step_type: str) -> int:
    if step_type.strip().lower() == "agent":
        return 0
    return 4


def _format_simple_output(text: str, *, step_type: str, theme: TuiTheme) -> str:
    if step_type.strip().lower() != "agent":
        return _indent_block(text, spaces=4)
    return text


def _prefix_agent_output(text: str, *, icon: str) -> str:
    lines = text.rstrip().splitlines()
    if not lines:
        return f"{icon} "

    prefixed: list[str] = []
    for index, line in enumerate(lines):
        if index == 0:
            prefixed.append(f"{icon} {line}" if line else f"{icon} ")
            continue
        prefixed.append(f"  {line}" if line else "")
    return "\n".join(prefixed)


def _render_inline_conditional_route(
    *,
    item: TranscriptItem,
    next_item: TranscriptItem,
    theme: TuiTheme,
) -> RenderableType | None:
    if not isinstance(item, RunStepItem):
        return None
    if not isinstance(next_item, RunOutputItem):
        return None
    if item.run_id != next_item.run_id:
        return None

    normalized_step_type = item.step_type.strip().lower()
    if normalized_step_type not in _INLINE_CONDITIONAL_STEP_TYPES:
        return None

    output_step_type = next_item.step_type.strip().lower()
    if output_step_type != normalized_step_type:
        return None

    target = _extract_conditional_target(next_item.output)
    if not target:
        return None

    return Text(
        f"   [{item.step_type}] {item.step_id} \u2192 {target}",
        style=theme.rich_style(theme.color_text_muted),
    )


def _extract_conditional_target(output: str) -> str:
    normalized = output.strip()
    if not normalized:
        return ""

    parsed = _try_parse_json_output(normalized)
    if isinstance(parsed, dict):
        value = parsed.get("value")
        if isinstance(value, dict):
            next_step_id = value.get("next_step_id")
            if isinstance(next_step_id, str) and next_step_id.strip():
                return next_step_id.strip()

        text = parsed.get("text")
        if isinstance(text, str):
            route_text_target = _extract_target_from_route_text(text)
            if route_text_target:
                return route_text_target

    return _extract_target_from_route_text(normalized)


def _extract_target_from_route_text(text: str) -> str:
    match = _ROUTE_SELECTED_RE.match(text)
    if match is None:
        return ""
    return match.group("target").strip()


def _indent_block(text: str, *, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in text.splitlines())


def _needs_separator(item: TranscriptItem, items: list[TranscriptItem], index: int) -> bool:
    next_item = _next_visible_item(items=items, start_index=index + 1)
    if next_item is None:
        return False
    if isinstance(item, (RunAckItem, DispatchErrorItem, UserInputItem)):
        return True
    if isinstance(item, AgentAssistantMessageItem):
        return item.message_type.strip().lower() == "final"
    if isinstance(item, AgentSystemNoticeItem):
        return True
    if isinstance(item, RunOutputItem):
        return item.step_type.strip().lower() == "agent"
    return False


def _needs_prefix_separator(*, items: list[TranscriptItem], index: int) -> bool:
    item = items[index]
    previous_item = _previous_visible_item(items=items, start_index=index - 1)
    if previous_item is None:
        return False
    return _is_tool_item(previous_item) and not _is_tool_item(item)


def _is_tool_item(item: TranscriptItem) -> bool:
    return isinstance(item, (AgentToolCallItem, AgentToolResultItem))


def _needs_blank_line_after_collapsed_conditional(
    *,
    items: list[TranscriptItem],
    next_index: int,
) -> bool:
    next_item = _next_visible_item(items=items, start_index=next_index)
    if next_item is None:
        return False
    if not isinstance(next_item, RunStepItem):
        return False
    return next_item.step_type.strip().lower() == "agent"


def _find_active_tool_call_index(items: list[TranscriptItem]) -> int | None:
    active_index: int | None = None
    for index, item in enumerate(items):
        if isinstance(item, RunStatusItem) and item.status.strip().lower() == "waiting":
            continue
        if isinstance(item, AgentToolCallItem):
            active_index = index
            continue
        if isinstance(item, AgentSystemNoticeItem):
            active_index = None
            continue
        if isinstance(item, RunOutputItem) and item.step_type.strip().lower() == "agent":
            active_index = None
    return active_index


def _next_visible_item(
    *,
    items: list[TranscriptItem],
    start_index: int,
) -> TranscriptItem | None:
    index = start_index
    while index < len(items):
        item = items[index]
        if isinstance(item, RunStatusItem) and item.status.strip().lower() == "waiting":
            index += 1
            continue
        return item
    return None


def _previous_visible_item(
    *,
    items: list[TranscriptItem],
    start_index: int,
) -> TranscriptItem | None:
    index = start_index
    while index >= 0:
        item = items[index]
        if isinstance(item, RunStatusItem) and item.status.strip().lower() == "waiting":
            index -= 1
            continue
        return item
    return None


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
