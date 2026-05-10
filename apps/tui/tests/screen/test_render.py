from __future__ import annotations

import pytest
from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.styled import Styled
from rich.table import Table
from rich.text import Text
from stui.screen.render import (
    _TrimLeadingBlankLines,
    render_transcript,
    render_transcript_item,
)
from stui.screen.theme import TuiTheme
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    OutputFormat,
    RunAckItem,
    RunOutputItem,
    RunResumeItem,
    RunStatusItem,
    RunStepItem,
    TranscriptMode,
    UserInputItem,
)

pytestmark = pytest.mark.unit

_SWITCH_ROUTE_OUTPUT = (
    '{"text":"Route selected: support_agent.",'
    '"value":{"next_step_id":"support_agent"}}'
)

_AGENT_SIMPLE_OUTPUT = (
    '{"body_ref":null,"text":"hello from agent",'
    '"value":{"data":{"final":{"text":"hello from agent"}}}}'
)


def _assert_prefixed_grid(renderable, *, prefix: str) -> object:  # noqa: ANN001
    assert isinstance(renderable, Table)
    assert len(renderable.columns) == 2
    assert renderable.columns[0].width == 1
    assert len(renderable.columns[0]._cells) == 1
    assert len(renderable.columns[1]._cells) == 1
    assert isinstance(renderable.columns[0]._cells[0], Text)
    assert renderable.columns[0]._cells[0].plain == prefix
    content = renderable.columns[1]._cells[0]
    assert isinstance(content, Padding)
    inner = content.renderable
    if isinstance(inner, _TrimLeadingBlankLines):
        return inner.renderable
    return inner


def _assert_agent_grid(renderable) -> object:  # noqa: ANN001
    return _assert_prefixed_grid(renderable, prefix="‹")


def test_render_transcript_item_renders_user_line_with_theme_icon() -> None:
    item = UserInputItem(text="hola mundo")
    theme = TuiTheme(user_icon="›", color_text_accent="#79c0ff")

    renderable = render_transcript_item(item, theme=theme)

    content = _assert_prefixed_grid(renderable, prefix="›")
    assert isinstance(content, Text)
    assert content.plain == "hola mundo"
    assert content.style == theme.rich_style(theme.color_text_accent)
    assert renderable.columns[0]._cells[0].style == theme.rich_style(theme.color_text_accent)


def test_render_transcript_uses_theme_icon_for_user_items() -> None:
    theme = TuiTheme(user_icon="»")

    renderables = render_transcript(
        items=[UserInputItem(text="hello")],
        theme=theme,
    )

    content = _assert_prefixed_grid(renderables[0], prefix="»")
    assert isinstance(content, Text)
    assert content.plain == "hello"


def test_render_transcript_item_renders_resume_header() -> None:
    theme = TuiTheme(color_text_muted="grey50")
    renderable = render_transcript_item(
        RunResumeItem(run_id="run-1", skill="wait_input_test"),
        theme=theme,
    )

    assert isinstance(renderable, Text)
    assert renderable.plain == "↳ resume(wait_input_test)"
    assert renderable.style == theme.rich_style(theme.color_text_muted)


def test_render_transcript_does_not_insert_blank_line_before_resume() -> None:
    renderables = render_transcript(
        items=[
            UserInputItem(text="hola"),
            RunResumeItem(run_id="run-1", skill="wait_input_test"),
        ],
    )

    assert len(renderables) == 3
    assert isinstance(renderables[0], Table)
    assert isinstance(renderables[1], Text)
    assert isinstance(renderables[2], Text)
    content = _assert_prefixed_grid(renderables[0], prefix="›")
    assert isinstance(content, Text)
    assert content.plain == "hola"
    assert renderables[1].plain == ""
    assert renderables[2].plain == "↳ resume(wait_input_test)"


def test_render_transcript_keeps_blank_line_between_command_and_run_ack() -> None:
    renderables = render_transcript(
        items=[
            UserInputItem(text="/run test"),
            RunAckItem(skill="test", run_id="run-1"),
        ],
    )

    assert len(renderables) == 3
    assert isinstance(renderables[0], Table)
    assert isinstance(renderables[1], Text)
    content = _assert_prefixed_grid(renderables[0], prefix="›")
    assert isinstance(content, Text)
    assert content.plain == "/run test"
    assert renderables[1].plain == ""


def test_render_transcript_inserts_blank_line_between_user_and_agent_step() -> None:
    renderables = render_transcript(
        items=[
            UserInputItem(text="hola"),
            RunStepItem(
                run_id="run-1",
                step_type="agent",
                step_id="support_agent",
            ),
        ],
    )

    assert len(renderables) == 3
    assert isinstance(renderables[0], Table)
    assert isinstance(renderables[1], Text)
    assert isinstance(renderables[2], Text)
    content = _assert_prefixed_grid(renderables[0], prefix="›")
    assert isinstance(content, Text)
    assert content.plain == "hola"
    assert renderables[1].plain == ""
    assert renderables[2].plain == "[agent] support_agent"


def test_render_transcript_inserts_blank_line_between_agent_reply_and_next_user_input() -> None:
    renderables = render_transcript(
        items=[
            RunStepItem(
                run_id="run-1",
                step_type="agent",
                step_id="support_agent",
            ),
            RunOutputItem(
                run_id="run-1",
                step_type="agent",
                output="Las arañas tienen 8 patas.",
            ),
            UserInputItem(text="en terminos de ojos ?"),
        ],
    )

    assert len(renderables) == 4
    assert isinstance(renderables[0], Text)
    assert isinstance(renderables[1], Table)
    assert isinstance(renderables[2], Text)
    assert isinstance(renderables[3], Table)
    assert renderables[0].plain == "[agent] support_agent"
    content = _assert_agent_grid(renderables[1])
    assert isinstance(content, Text)
    assert content.plain == "Las arañas tienen 8 patas."
    assert renderables[2].plain == ""
    content = _assert_prefixed_grid(renderables[3], prefix="›")
    assert isinstance(content, Text)
    assert content.plain == "en terminos de ojos ?"


def test_render_transcript_inserts_blank_line_after_agent_reply_even_with_waiting_status() -> None:
    renderables = render_transcript(
        items=[
            RunStepItem(
                run_id="run-1",
                step_type="agent",
                step_id="support_agent",
            ),
            RunOutputItem(
                run_id="run-1",
                step_type="agent",
                output="Las arañas suelen tener 8 ojos.",
            ),
            RunStatusItem(
                run_id="run-1",
                status="waiting",
            ),
            UserInputItem(text="y que pasa con los oidos ?"),
        ],
    )

    assert len(renderables) == 4
    assert isinstance(renderables[0], Text)
    assert isinstance(renderables[1], Table)
    assert isinstance(renderables[2], Text)
    assert isinstance(renderables[3], Table)
    assert renderables[0].plain == "[agent] support_agent"
    content = _assert_agent_grid(renderables[1])
    assert isinstance(content, Text)
    assert content.plain == "Las arañas suelen tener 8 ojos."
    assert renderables[2].plain == ""
    content = _assert_prefixed_grid(renderables[3], prefix="›")
    assert isinstance(content, Text)
    assert content.plain == "y que pasa con los oidos ?"


def test_render_transcript_inserts_blank_line_between_tool_result_and_agent_reply() -> None:
    renderables = render_transcript(
        items=[
            RunStepItem(
                run_id="run-1",
                step_type="agent",
                step_id="support_agent",
            ),
            AgentToolCallItem(
                run_id="run-1",
                step_id="support_agent",
                tool="shell",
                command='echo "hola mundo"',
            ),
            AgentToolResultItem(
                run_id="run-1",
                tool="shell",
                preview="Command completed successfully.",
            ),
            RunOutputItem(
                run_id="run-1",
                step_type="agent",
                output="Cambios aplicados.",
            ),
        ],
    )

    assert len(renderables) == 5
    assert isinstance(renderables[0], Text)
    assert isinstance(renderables[1], Table)
    assert isinstance(renderables[2], Padding)
    assert isinstance(renderables[3], Text)
    assert isinstance(renderables[4], Table)
    assert renderables[0].plain == "[agent] support_agent"
    assert isinstance(renderables[1].columns[1]._cells[0], Padding)
    assert isinstance(renderables[1].columns[1]._cells[0].renderable, Text)
    assert renderables[1].columns[1]._cells[0].renderable.plain == '$ echo "hola mundo"'
    assert isinstance(renderables[2].renderable, Text)
    assert renderables[2].renderable.plain == "Command completed successfully."
    assert renderables[3].plain == ""
    content = _assert_agent_grid(renderables[4])
    assert isinstance(content, Text)
    assert content.plain == "Cambios aplicados."


def test_render_transcript_inserts_blank_line_between_tool_result_and_agent_assistant_message(
) -> None:
    renderables = render_transcript(
        items=[
            RunStepItem(
                run_id="run-1",
                step_type="agent",
                step_id="support_agent",
            ),
            AgentToolCallItem(
                run_id="run-1",
                step_id="support_agent",
                tool="shell",
                command='echo "hola mundo"',
            ),
            AgentToolResultItem(
                run_id="run-1",
                tool="shell",
                preview="Command completed successfully.",
            ),
            AgentAssistantMessageItem(
                run_id="run-1",
                step_id="support_agent",
                message_type="tool_calls",
                text="Ahora voy a revisar el siguiente comando.",
            ),
        ],
    )

    assert len(renderables) == 5
    assert isinstance(renderables[0], Text)
    assert isinstance(renderables[1], Table)
    assert isinstance(renderables[2], Padding)
    assert isinstance(renderables[3], Text)
    assert isinstance(renderables[4], Table)
    assert renderables[0].plain == "[agent] support_agent"
    assert isinstance(renderables[1].columns[1]._cells[0], Padding)
    assert isinstance(renderables[1].columns[1]._cells[0].renderable, Text)
    assert renderables[1].columns[1]._cells[0].renderable.plain == '$ echo "hola mundo"'
    assert isinstance(renderables[2].renderable, Text)
    assert renderables[2].renderable.plain == "Command completed successfully."
    assert renderables[3].plain == ""
    content = _assert_agent_grid(renderables[4])
    assert isinstance(content, Styled)
    assert isinstance(content.renderable, Markdown)
    assert content.renderable.markup == "Ahora voy a revisar el siguiente comando."


def test_render_transcript_inserts_blank_line_after_final_agent_assistant_message() -> None:
    renderables = render_transcript(
        items=[
            RunStepItem(
                run_id="run-1",
                step_type="agent",
                step_id="support_agent",
            ),
            AgentAssistantMessageItem(
                run_id="run-1",
                step_id="support_agent",
                message_type="final",
                text="Hecho.",
            ),
            UserInputItem(text="sigue"),
        ],
    )

    assert len(renderables) == 4
    assert isinstance(renderables[0], Text)
    assert isinstance(renderables[1], Table)
    assert isinstance(renderables[2], Text)
    assert isinstance(renderables[3], Table)
    assert renderables[0].plain == "[agent] support_agent"
    content = _assert_agent_grid(renderables[1])
    assert isinstance(content, Markdown)
    assert content.markup == "Hecho."
    assert renderables[2].plain == ""
    content = _assert_prefixed_grid(renderables[3], prefix="›")
    assert isinstance(content, Text)
    assert content.plain == "sigue"


def test_render_transcript_inserts_blank_line_after_agent_system_notice() -> None:
    renderables = render_transcript(
        items=[
            RunStepItem(
                run_id="run-1",
                step_type="agent",
                step_id="support_agent",
            ),
            AgentSystemNoticeItem(
                run_id="run-1",
                step_id="support_agent",
                text="Interrupted by user",
            ),
            UserInputItem(text="continua"),
        ],
    )

    assert len(renderables) == 4
    assert isinstance(renderables[0], Text)
    assert isinstance(renderables[1], Table)
    assert isinstance(renderables[2], Text)
    assert isinstance(renderables[3], Table)
    assert renderables[0].plain == "[agent] support_agent"
    content = _assert_prefixed_grid(renderables[1], prefix="!")
    assert isinstance(content, Text)
    assert content.plain == "Interrupted by user"
    assert renderables[2].plain == ""
    content = _assert_prefixed_grid(renderables[3], prefix="›")
    assert isinstance(content, Text)
    assert content.plain == "continua"


def test_render_transcript_collapses_switch_route_in_single_muted_suffix_line() -> None:
    theme = TuiTheme(color_text_muted="grey50")
    renderables = render_transcript(
        items=[
            RunStepItem(
                run_id="run-1",
                step_type="switch",
                step_id="decide_exit",
            ),
            RunOutputItem(
                run_id="run-1",
                step_type="switch",
                output=_SWITCH_ROUTE_OUTPUT,
            ),
        ],
        theme=theme,
    )

    assert len(renderables) == 1
    assert isinstance(renderables[0], Text)
    assert renderables[0].plain == "   [switch] decide_exit → support_agent"
    assert renderables[0].style == theme.rich_style(theme.color_text_muted)


def test_render_transcript_inserts_blank_line_between_collapsed_switch_and_agent_step() -> None:
    renderables = render_transcript(
        items=[
            RunStepItem(
                run_id="run-1",
                step_type="switch",
                step_id="decide_exit",
            ),
            RunOutputItem(
                run_id="run-1",
                step_type="switch",
                output=_SWITCH_ROUTE_OUTPUT,
            ),
            RunStepItem(
                run_id="run-1",
                step_type="agent",
                step_id="support_agent",
            ),
        ],
    )

    assert len(renderables) == 3
    assert isinstance(renderables[0], Text)
    assert isinstance(renderables[1], Text)
    assert isinstance(renderables[2], Text)
    assert renderables[0].plain == "   [switch] decide_exit → support_agent"
    assert renderables[1].plain == ""
    assert renderables[2].plain == "[agent] support_agent"


def test_render_transcript_collapses_when_route_in_single_muted_suffix_line() -> None:
    theme = TuiTheme(color_text_muted="grey50")
    renderables = render_transcript(
        items=[
            RunStepItem(
                run_id="run-1",
                step_type="when",
                step_id="check_route",
            ),
            RunOutputItem(
                run_id="run-1",
                step_type="when",
                output=(
                    '{"text":"Route selected: default_route.",'
                    '"value":{"next_step_id":"default_route"}}'
                ),
            ),
        ],
        theme=theme,
    )

    assert len(renderables) == 1
    assert isinstance(renderables[0], Text)
    assert renderables[0].plain == "   [when] check_route → default_route"
    assert renderables[0].style == theme.rich_style(theme.color_text_muted)


def test_render_transcript_item_renders_agent_step_with_accent_tag() -> None:
    theme = TuiTheme(color_text_accent="magenta", color_text_secondary="grey70")
    renderable = render_transcript_item(
        RunStepItem(
            run_id="run-1",
            step_type="agent",
            step_id="support_agent",
        ),
        theme=theme,
    )

    assert isinstance(renderable, Text)
    assert renderable.plain == "[agent] support_agent"
    assert any(
        span.start == 1
        and span.end == 6
        and span.style == theme.rich_style(theme.color_text_accent)
        for span in renderable.spans
    )
    assert any(
        span.start == 8
        and span.end == len("[agent] support_agent")
        and span.style == theme.rich_style(theme.color_text_secondary)
        for span in renderable.spans
    )


def test_render_transcript_item_renders_agent_step_muted_in_chat_mode() -> None:
    theme = TuiTheme(color_text_muted="grey50")
    renderable = render_transcript_item(
        RunStepItem(
            run_id="run-1",
            step_type="agent",
            step_id="support_agent",
        ),
        mode=TranscriptMode.CHAT,
        theme=theme,
    )

    assert isinstance(renderable, Text)
    assert renderable.plain == "[agent] support_agent"
    assert any(
        span.start == 0
        and span.end == 1
        and span.style == f"{theme.rich_style(theme.color_text_muted)} dim"
        for span in renderable.spans
    )
    assert any(
        span.start == 1
        and span.end == 6
        and span.style == f"{theme.rich_style(theme.color_text_muted)} dim"
        for span in renderable.spans
    )
    assert any(
        span.start == 6
        and span.end == 8
        and span.style == f"{theme.rich_style(theme.color_text_muted)} dim"
        for span in renderable.spans
    )
    assert any(
        span.start == 8
        and span.end == len("[agent] support_agent")
        and span.style == f"{theme.rich_style(theme.color_text_muted)} dim"
        for span in renderable.spans
    )


def test_render_transcript_item_renders_agent_tool_call_with_muted_square_icon() -> None:
    theme = TuiTheme(agent_tool_icon="▪", color_text_muted="grey50")
    renderable = render_transcript_item(
        AgentToolCallItem(
            run_id="run-1",
            step_id="support_agent",
            tool="shell",
            command="git status --short",
        ),
        theme=theme,
    )

    assert isinstance(renderable, Table)
    assert len(renderable.columns) == 2
    assert renderable.columns[0].width == 1
    assert isinstance(renderable.columns[0]._cells[0], Text)
    assert renderable.columns[0]._cells[0].plain == "▪"
    assert renderable.columns[0]._cells[0].style == theme.rich_style(theme.color_text_muted)
    assert isinstance(renderable.columns[1]._cells[0], Padding)
    assert isinstance(renderable.columns[1]._cells[0].renderable, Text)
    assert renderable.columns[1]._cells[0].renderable.plain == "$ git status --short"
    assert (
        renderable.columns[1]._cells[0].renderable.style
        == theme.rich_style(theme.color_text_muted)
    )


def test_render_transcript_item_renders_active_agent_tool_call_in_primary_text() -> None:
    theme = TuiTheme(
        agent_tool_icon="▪",
        color_text_muted="grey50",
        color_text_primary="#e6edf3",
    )
    renderable = render_transcript_item(
        AgentToolCallItem(
            run_id="run-1",
            step_id="support_agent",
            tool="shell",
            command="git status --short",
        ),
        theme=theme,
        is_active_tool_call=True,
    )

    assert isinstance(renderable, Table)
    assert isinstance(renderable.columns[0]._cells[0], Text)
    assert renderable.columns[0]._cells[0].style == theme.rich_style(theme.color_text_primary)
    assert isinstance(renderable.columns[1]._cells[0], Padding)
    assert isinstance(renderable.columns[1]._cells[0].renderable, Text)
    assert (
        renderable.columns[1]._cells[0].renderable.style
        == theme.rich_style(theme.color_text_primary)
    )


def test_render_transcript_item_renders_agent_tool_result_in_muted_text() -> None:
    theme = TuiTheme(color_text_muted="grey50")
    renderable = render_transcript_item(
        AgentToolResultItem(
            run_id="run-1",
            tool="shell",
            preview="M docs/configuration.md",
        ),
        theme=theme,
    )

    assert isinstance(renderable, Padding)
    assert isinstance(renderable.renderable, Text)
    assert renderable.renderable.plain == "M docs/configuration.md"
    assert renderable.renderable.style == theme.rich_style(theme.color_text_muted)
    assert renderable.left == 4


def test_render_transcript_marks_only_last_unresolved_tool_call_as_active() -> None:
    theme = TuiTheme(
        agent_tool_icon="▪",
        color_text_muted="grey50",
        color_text_primary="#e6edf3",
    )

    renderables = render_transcript(
        items=[
            AgentToolCallItem(
                run_id="run-1",
                step_id="support_agent",
                tool="shell",
                command="first",
            ),
            AgentToolResultItem(
                run_id="run-1",
                tool="shell",
                preview="ok",
            ),
            AgentToolCallItem(
                run_id="run-1",
                step_id="support_agent",
                tool="shell",
                command="second",
            ),
        ],
        theme=theme,
    )

    first = renderables[0]
    second = renderables[2]
    assert isinstance(first, Table)
    assert isinstance(second, Table)
    assert first.columns[0]._cells[0].style == theme.rich_style(theme.color_text_muted)
    assert second.columns[0]._cells[0].style == theme.rich_style(theme.color_text_primary)


def test_render_transcript_clears_active_tool_call_after_agent_final_output() -> None:
    theme = TuiTheme(
        agent_tool_icon="▪",
        color_text_muted="grey50",
        color_text_primary="#e6edf3",
    )

    renderables = render_transcript(
        items=[
            AgentToolCallItem(
                run_id="run-1",
                step_id="support_agent",
                tool="shell",
                command="first",
            ),
            RunOutputItem(
                run_id="run-1",
                step_type="agent",
                output="done",
            ),
        ],
        theme=theme,
    )

    first = renderables[0]
    assert isinstance(first, Table)
    assert first.columns[0]._cells[0].style == theme.rich_style(theme.color_text_muted)


def test_render_transcript_clears_active_tool_call_after_agent_system_notice() -> None:
    theme = TuiTheme(
        agent_tool_icon="▪",
        color_text_muted="grey50",
        color_text_primary="#e6edf3",
    )

    renderables = render_transcript(
        items=[
            AgentToolCallItem(
                run_id="run-1",
                step_id="support_agent",
                tool="shell",
                command="first",
            ),
            AgentSystemNoticeItem(
                run_id="run-1",
                step_id="support_agent",
                text="Interrupted by user",
            ),
        ],
        theme=theme,
    )

    first = renderables[0]
    assert isinstance(first, Table)
    assert first.columns[0]._cells[0].style == theme.rich_style(theme.color_text_muted)


def test_render_transcript_item_folds_long_tool_result_tokens_instead_of_truncating() -> None:
    renderable = render_transcript_item(
        AgentToolResultItem(
            run_id="run-1",
            tool="shell",
            preview=(
                "packages/skiller/src/skiller/di/container.py:109:"
                "tool_execution=InProcessToolExecution"
            ),
        )
    )

    console = Console(width=70, record=True)
    console.print(renderable)
    exported = console.export_text()

    assert "..." not in exported
    assert "tool_execution=" in exported
    assert "tool_execution=In" in exported
    assert "ProcessToolExecution" in exported


def test_render_transcript_item_renders_agent_assistant_message_as_agent_output() -> None:
    theme = TuiTheme(
        agent_message_icon="‹",
        color_text_muted="grey50",
        color_text_secondary="grey70",
    )
    renderable = render_transcript_item(
        AgentAssistantMessageItem(
            run_id="run-1",
            step_id="support_agent",
            message_type="tool_calls",
            text="I will inspect the repository state.",
        ),
        theme=theme,
    )

    content = _assert_agent_grid(renderable)
    assert isinstance(content, Styled)
    assert content.style == theme.rich_style(theme.color_text_secondary)
    assert isinstance(content.renderable, Markdown)
    assert content.renderable.markup == "I will inspect the repository state."


def test_render_transcript_item_renders_agent_system_notice_in_warning_color() -> None:
    theme = TuiTheme(system_warning_icon="!", color_text_warning="#d29922")
    renderable = render_transcript_item(
        AgentSystemNoticeItem(
            run_id="run-1",
            step_id="support_agent",
            text="Turn limit reached",
        ),
        theme=theme,
    )

    content = _assert_prefixed_grid(renderable, prefix="!")
    assert isinstance(content, Text)
    assert content.plain == "Turn limit reached"
    assert content.style == theme.rich_style(theme.color_text_warning)


def test_render_transcript_item_keeps_final_agent_assistant_message_unmuted() -> None:
    theme = TuiTheme(agent_message_icon="‹", color_text_muted="grey50")
    renderable = render_transcript_item(
        AgentAssistantMessageItem(
            run_id="run-1",
            step_id="support_agent",
            message_type="final",
            text="Done.",
        ),
        theme=theme,
    )

    content = _assert_agent_grid(renderable)
    assert isinstance(content, Markdown)
    assert content.markup == "Done."


def test_render_transcript_item_renders_agent_output_as_simple_text() -> None:
    theme = TuiTheme(agent_message_icon="‹")
    renderable = render_transcript_item(
        RunOutputItem(
            run_id="run-1",
            step_type="agent",
            output=_AGENT_SIMPLE_OUTPUT,
        ),
        theme=theme,
    )

    content = _assert_agent_grid(renderable)
    assert isinstance(content, Text)
    assert content.plain == "hello from agent"


def test_render_transcript_item_strips_trailing_blank_line_from_agent_output() -> None:
    theme = TuiTheme(agent_message_icon="‹")
    renderable = render_transcript_item(
        RunOutputItem(
            run_id="run-1",
            step_type="agent",
            output="hello from agent\n",
        ),
        theme=theme,
    )

    content = _assert_agent_grid(renderable)
    assert isinstance(content, Text)
    assert content.plain == "hello from agent"


def test_render_transcript_item_indents_all_lines_for_simple_multiline_output() -> None:
    theme = TuiTheme(agent_message_icon="‹")
    renderable = render_transcript_item(
        RunOutputItem(
            run_id="run-1",
            step_type="agent",
            output="Hay cambios:\n\n- **42 cambios**\n- **14 tests**",
        ),
        theme=theme,
    )

    content = _assert_agent_grid(renderable)
    assert isinstance(content, Text)
    assert content.plain == "Hay cambios:\n\n- **42 cambios**\n- **14 tests**"


def test_render_transcript_item_renders_markdown_output_when_format_is_markdown() -> None:
    theme = TuiTheme(agent_message_icon="‹")
    renderable = render_transcript_item(
        RunOutputItem(
            run_id="run-1",
            step_type="agent",
            output='{"text":"Hay cambios:\\n\\n- **42 cambios**\\n- **14 tests**"}',
            format=OutputFormat.MARKDOWN,
        ),
        theme=theme,
    )

    content = _assert_agent_grid(renderable)
    assert isinstance(content, Markdown)
    assert content.markup == "Hay cambios:\n\n- **42 cambios**\n- **14 tests**"


def test_render_transcript_item_separates_agent_markdown_fenced_code_block() -> None:
    theme = TuiTheme(agent_message_icon="‹")
    renderable = render_transcript_item(
        RunOutputItem(
            run_id="run-1",
            step_type="agent",
            output=(
                '{"text":"Cambios aplicados:\\n\\n```diff\\n@@ -1 +1 @@\\n-old\\n+new\\n```"}'
            ),
            format=OutputFormat.MARKDOWN,
        ),
        theme=theme,
    )

    content = _assert_agent_grid(renderable)
    assert isinstance(content, Markdown)
    assert content.markup == "Cambios aplicados:\n\n```diff\n@@ -1 +1 @@\n-old\n+new\n```"


def test_render_transcript_item_places_agent_icon_first_when_markdown_starts_with_code() -> None:
    theme = TuiTheme(agent_message_icon="‹")
    renderable = render_transcript_item(
        RunOutputItem(
            run_id="run-1",
            step_type="agent",
            output=(
                '{"text":"```diff\\n@@ -1 +1 @@\\n-old\\n+new\\n```\\n\\nCambios:\\n\\n1. Uno"}'
            ),
            format=OutputFormat.MARKDOWN,
        ),
        theme=theme,
    )

    content = _assert_agent_grid(renderable)
    assert isinstance(content, Markdown)
    assert content.markup == "```diff\n@@ -1 +1 @@\n-old\n+new\n```\n\nCambios:\n\n1. Uno"


def test_render_transcript_item_does_not_prefix_agent_icon_when_markdown_starts_with_table(
) -> None:
    theme = TuiTheme(agent_message_icon="‹")
    renderable = render_transcript_item(
        RunOutputItem(
            run_id="run-1",
            step_type="agent",
            output=(
                '{"text":"| Archivo | Caracteres |\\n'
                '|---------|------------|\\n'
                '| a.md | 10 |\\n\\nTotal: 1"}'
            ),
            format=OutputFormat.MARKDOWN,
        ),
        theme=theme,
    )

    content = _assert_agent_grid(renderable)
    assert isinstance(content, Markdown)
    assert content.markup == (
        "| Archivo | Caracteres |\n"
        "|---------|------------|\n"
        "| a.md | 10 |\n\n"
        "Total: 1"
    )


def test_render_transcript_item_renders_wait_step_as_muted_placeholder() -> None:
    renderable = render_transcript_item(
        RunStepItem(
            run_id="run-1",
            step_type="wait_input",
            step_id="ask_user",
        ),
    )

    assert isinstance(renderable, Text)
    assert renderable.plain == "   ..."


def test_render_transcript_skips_run_waiting_status_line() -> None:
    renderables = render_transcript(
        items=[
            RunStepItem(run_id="run-1", step_type="wait_input", step_id="ask_user"),
            RunStatusItem(run_id="run-1", status="waiting"),
        ],
    )

    assert len(renderables) == 1
    assert isinstance(renderables[0], Text)
    assert renderables[0].plain == "   ..."
