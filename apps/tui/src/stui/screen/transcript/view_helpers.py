from __future__ import annotations

import json
from dataclasses import dataclass

from rich.console import RenderableType
from rich.padding import Padding
from rich.pretty import Pretty
from rich.segment import Segment, Segments
from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from stui.screen.markdown import MarkdownView
from stui.screen.theme import TuiTheme
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    OutputFormat,
    TranscriptMode,
)


def transcript_text(value: str, *, style: str = "") -> Text:
    return Text(
        value,
        style=style,
        overflow="fold",
        no_wrap=False,
    )


def prefixed_view(
    *,
    prefix: RenderableType,
    content: RenderableType,
    prefix_width: int = 1,
) -> RenderableType:
    grid = Table.grid(padding=(0, 0))
    grid.add_column(width=prefix_width)
    grid.add_column()
    grid.add_row(prefix, Padding(content, (0, 0, 0, 1)))
    return grid


def agent_step_tag_style(*, theme: TuiTheme, mode: TranscriptMode) -> str:
    if mode == TranscriptMode.CHAT:
        base_style = theme.color_text_muted
        return f"{base_style} dim".strip()
    return theme.color_text_accent


def agent_step_id_style(*, theme: TuiTheme, mode: TranscriptMode) -> str:
    if mode == TranscriptMode.CHAT:
        base_style = theme.color_text_muted
        return f"{base_style} dim".strip()
    return theme.color_text_secondary


def render_run_output(
    *,
    theme: TuiTheme,
    step_type: str,
    output: str,
    format: OutputFormat,
) -> RenderableType:
    normalized = output.strip()
    if not normalized:
        return Text("")

    parsed = try_parse_json_output(normalized)
    indent = output_indent(step_type)
    if format == OutputFormat.SIMPLE:
        rendered_simple = render_simple_output(normalized, parsed)
        if rendered_simple:
            if step_type.strip().lower() == "agent":
                return wrap_agent_renderable(Text(rendered_simple), theme=theme)
            return Text(format_simple_output(rendered_simple, step_type=step_type))
        if step_type.strip().lower() == "agent":
            return wrap_agent_renderable(Text(normalized), theme=theme)
        return Text(format_simple_output(normalized, step_type=step_type))

    if format == OutputFormat.MARKDOWN:
        if step_type.strip().lower() == "agent":
            return wrap_agent_renderable(
                render_agent_content(
                    output=normalized,
                    format=format,
                    theme=theme,
                    parsed=parsed,
                ),
                theme=theme,
            )
        return render_markdown_output(
            normalized,
            parsed,
            theme=theme,
            indent=indent,
        )

    if format == OutputFormat.STRUCTURED:
        return render_structured_output(parsed, normalized, indent=indent)

    if parsed is None:
        return Text(format_simple_output(normalized, step_type=step_type))
    return render_structured_output(parsed, normalized, indent=indent)


def render_agent_assistant_content(
    *,
    item: AgentAssistantMessageItem,
    theme: TuiTheme,
) -> RenderableType:
    renderable = render_agent_content(
        output=item.text,
        format=item.format,
        theme=theme,
    )
    if item.message_type.strip().lower() == "final":
        return renderable
    return Styled(
        renderable,
        style=theme.color_text_secondary,
    )


def wrap_agent_renderable(
    renderable: RenderableType,
    *,
    theme: TuiTheme,
) -> RenderableType:
    return prefixed_view(
        prefix=transcript_text(
            theme.agent_message_icon,
            style=theme.color_text_primary,
        ),
        content=TrimLeadingBlankLines(renderable),
        prefix_width=1,
    )


def strip_error_prefix(message: str) -> str:
    normalized = message.strip()
    if normalized.lower().startswith("error:"):
        return normalized[6:].strip()
    return normalized


def render_simple_output(normalized: str, parsed: object | None) -> str:
    if parsed is None:
        return normalized
    if isinstance(parsed, dict):
        text = parsed.get("text")
        if isinstance(text, str):
            stripped = text.strip()
            if stripped:
                return stripped
    return normalized


def render_structured_output(
    parsed: object | None,
    normalized: str,
    *,
    indent: int,
) -> RenderableType:
    if parsed is None:
        return Text(indent_block(normalized, spaces=indent))

    render_value = parsed
    if isinstance(parsed, dict) and "value" in parsed:
        render_value = parsed["value"]

    return Padding(
        Pretty(render_value, indent_guides=False, expand_all=True),
        (0, 0, 0, indent),
    )


def render_markdown_output(
    normalized: str,
    parsed: object | None,
    *,
    theme: TuiTheme,
    indent: int,
) -> RenderableType:
    markdown_text = extract_markdown_text(normalized, parsed)
    if not markdown_text.strip():
        return Text("")
    return Padding(
        MarkdownView(markdown_text, theme=theme).render(),
        (0, 0, 0, indent),
    )


def render_agent_content(
    *,
    output: str,
    format: OutputFormat,
    theme: TuiTheme,
    parsed: object | None = None,
) -> RenderableType:
    normalized = output.strip()
    if not normalized:
        return Text("")

    resolved_parsed = parsed
    if resolved_parsed is None:
        resolved_parsed = try_parse_json_output(normalized)

    if format == OutputFormat.MARKDOWN:
        markdown_text = extract_markdown_text(normalized, resolved_parsed)
        return MarkdownView(markdown_text, theme=theme).render()

    if format == OutputFormat.STRUCTURED:
        return render_structured_output(resolved_parsed, normalized, indent=0)

    rendered_simple = render_simple_output(normalized, resolved_parsed)
    return Text(rendered_simple or normalized)


def extract_markdown_text(normalized: str, parsed: object | None) -> str:
    if isinstance(parsed, dict):
        text = parsed.get("text")
        if isinstance(text, str):
            return text
    return normalized


@dataclass(frozen=True)
class TrimLeadingBlankLines:
    renderable: RenderableType

    def __rich_console__(self, console, options):  # noqa: ANN001
        lines = console.render_lines(self.renderable, options, pad=False)
        while lines and line_is_blank(lines[0]):
            lines.pop(0)
        while lines and line_is_blank(lines[-1]):
            lines.pop()
        if not lines:
            return

        for index, line in enumerate(lines):
            yield Segments(line)
            if index < len(lines) - 1:
                yield Segment.line()


def line_is_blank(line: list[Segment]) -> bool:
    return not "".join(segment.text for segment in line).strip()


def output_indent(step_type: str) -> int:
    if step_type.strip().lower() == "agent":
        return 0
    return 4


def format_simple_output(text: str, *, step_type: str) -> str:
    if step_type.strip().lower() != "agent":
        return indent_block(text, spaces=4)
    return text


def indent_block(text: str, *, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in text.splitlines())


def try_parse_json_output(output: str) -> object | None:
    if not output.startswith(("{", "[")):
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None
