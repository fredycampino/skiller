from __future__ import annotations

from rich.console import Console

from stui.screen.markdown import MarkdownView


def test_markdown_view_renders_h1_left_aligned() -> None:
    console = Console(width=40, force_terminal=True, color_system=None)

    lines = console.render_lines(
        MarkdownView("# Skiller is ready").render(),
        console.options,
        pad=False,
    )

    assert lines
    assert "".join(segment.text for segment in lines[0]).startswith("Skiller is ready")


def test_markdown_view_renders_h1_without_underline() -> None:
    console = Console(width=40, force_terminal=True, color_system=None)

    lines = console.render_lines(
        MarkdownView("# Configure an LLM provider").render(),
        console.options,
        pad=False,
    )

    assert lines
    assert all(not segment.style or not segment.style.underline for segment in lines[0])


def test_markdown_view_renders_h1_with_secondary_accent() -> None:
    console = Console(width=40, force_terminal=True, color_system=None)

    lines = console.render_lines(
        MarkdownView("# Configure an LLM provider").render(),
        console.options,
        pad=False,
    )

    assert lines
    heading_segment = next(segment for segment in lines[0] if segment.text.strip())
    assert heading_segment.style is not None
    assert heading_segment.style.color is not None
    assert heading_segment.style.color.triplet is not None
    assert heading_segment.style.color.triplet.hex == "#b48ead"
