from __future__ import annotations

import asyncio
from typing import Any

from skiller.interfaces.ui.actions import ActionResult, handle_command, poll_run_progress
from skiller.interfaces.ui.commands import (
    InputCommand,
    RunCommand,
    UiCommand,
    parse_command,
)
from skiller.interfaces.ui.runtime_adapter import CliRuntimeAdapter
from skiller.interfaces.ui.session import UiRun, UiSession, build_session
from skiller.interfaces.ui.theme import build_prompt_toolkit_style_dict, theme
from skiller.interfaces.ui.tui_completer import (
    build_prompt_toolkit_completer,
    get_command_completion_prefix,
)
from skiller.interfaces.ui.tui_render import (
    build_footer_line,
    build_header_meta_line,
    build_header_title_line,
    build_initial_output,
    build_pending_input_status_text,
    build_pending_status_text,
    build_result_status_text,
    build_status_line,
    render_result_for_buffer,
)

_RUN_PROGRESS_ACTIVE_STATUSES = {"CREATED", "RUNNING"}
_RUN_PROGRESS_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}
_RUN_PROGRESS_POLL_INTERVAL_SECONDS = 0.1


def get_selected_waiting_input_run(session: UiSession) -> UiRun | None:
    selected_run_id = session.selected_run_id
    if selected_run_id is None:
        return None

    run = session.find_run(selected_run_id)
    if run is None or run.run_id is None:
        return None
    if run.status.upper() != "WAITING":
        return None

    wait_type = str(run.last_payload.get("wait_type", "")).strip().lower()
    prompt = str(run.last_payload.get("prompt", "")).strip()
    if wait_type != "input" or not prompt:
        return None
    return run


def should_submit_on_enter(text: str, *, waiting_input: bool = False) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if "\n" in text:
        return False
    if normalized.startswith("/"):
        return True
    if waiting_input:
        return True
    return normalized.lower() in {"exit", "quit"}


def has_active_completion(buffer: Any) -> bool:
    command_prefix = get_command_completion_prefix(buffer.document.text_before_cursor)
    if command_prefix is None:
        return False
    complete_state = getattr(buffer, "complete_state", None)
    if complete_state is None:
        return False
    return bool(complete_state.completions)


def accept_completion(buffer: Any) -> bool:
    command_prefix = get_command_completion_prefix(buffer.document.text_before_cursor)
    if command_prefix is None:
        return False
    complete_state = getattr(buffer, "complete_state", None)
    if complete_state is None or not complete_state.completions:
        return False

    if complete_state.current_completion is None:
        buffer.complete_next(count=1)
        complete_state = buffer.complete_state

    current_completion = None if complete_state is None else complete_state.current_completion
    if current_completion is None:
        return False

    buffer.apply_completion(current_completion)
    return True


def build_status_fragments(status_line: str) -> Any:
    if status_line.startswith("× Error"):
        return [("class:status.error", status_line)]
    return status_line


def build_submit_command(*, session: UiSession, text: str) -> UiCommand:
    waiting_run = get_selected_waiting_input_run(session)
    normalized = text.strip()
    if waiting_run is not None and normalized and not normalized.startswith("/"):
        return InputCommand(run_id=waiting_run.run_id or "", text=text)
    return parse_command(f"{text}\n")


def build_empty_reply_result(*, run: UiRun) -> ActionResult:
    return ActionResult(
        kind="input",
        run=run,
        payload={"accepted": False, "error": "reply text is required"},
    )


def should_refresh_after_input(result: ActionResult) -> bool:
    payload = result.payload or {}
    return (
        result.kind == "input"
        and bool(payload.get("accepted"))
        and not bool(payload.get("error"))
    )


def should_refresh_after_run(result: ActionResult) -> bool:
    run = result.run
    if result.kind != "run" or run is None or run.error or run.run_id is None:
        return False
    return run.status.upper() in _RUN_PROGRESS_ACTIVE_STATUSES


def build_progress_render_result(
    *,
    result: ActionResult,
    previous_status: str = "",
) -> ActionResult | None:
    run = result.run
    if result.kind != "watch" or run is None:
        return None

    events = result.payload.get("events") if isinstance(result.payload, dict) else None
    if isinstance(events, list) and events:
        return result

    current_status = run.status.upper()
    if current_status in _RUN_PROGRESS_TERMINAL_STATUSES and current_status != previous_status:
        return ActionResult(kind="status", run=run, payload=result.payload)
    return None


def build_output_wrap_prefix(
    *,
    text: str,
    line_number: int,
    wrap_count: int,
) -> str:
    if wrap_count <= 0:
        return ""

    lines = text.splitlines()
    if line_number < 0 or line_number >= len(lines):
        return ""

    line = lines[line_number]
    indent_width = len(line) - len(line.lstrip(" "))
    if indent_width <= 0:
        return ""
    return " " * indent_width


def run_prompt_toolkit_ui(
    *,
    session_key: str | None = None,
    runtime_adapter: CliRuntimeAdapter | None = None,
) -> str:
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.cursor_shapes import CursorShape
        from prompt_toolkit.document import Document
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
        from prompt_toolkit.layout.containers import Float, FloatContainer
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.margins import ScrollbarMargin
        from prompt_toolkit.layout.menus import CompletionsMenu
        from prompt_toolkit.patch_stdout import patch_stdout
        from prompt_toolkit.styles import Style
        from prompt_toolkit.widgets import TextArea
    except ImportError as exc:
        raise RuntimeError("prompt_toolkit is not installed") from exc

    session = build_session(session_key)
    runtime = runtime_adapter or CliRuntimeAdapter()
    output_text = build_initial_output(session=session)
    status_text = "Idle"
    status_busy = False
    active_follow_task: asyncio.Task[None] | None = None
    active_follow_run_id: str | None = None

    output_area = TextArea(
        text=output_text,
        read_only=True,
        focusable=False,
        scrollbar=False,
        wrap_lines=True,
        dont_extend_height=True,
    )
    output_area.window.right_margins = [ScrollbarMargin(display_arrows=False)]
    output_area.window.get_line_prefix = lambda line_number, wrap_count: build_output_wrap_prefix(
        text=output_area.text,
        line_number=line_number,
        wrap_count=wrap_count,
    )
    input_area = TextArea(
        prompt="> ",
        multiline=True,
        wrap_lines=True,
        completer=build_prompt_toolkit_completer(),
        complete_while_typing=True,
    )

    def set_output_text(text: str) -> None:
        output_area.buffer.set_document(
            Document(text=text, cursor_position=len(text)),
            bypass_readonly=True,
        )

    def apply_result(result: ActionResult) -> None:
        nonlocal output_text
        rendered = render_result_for_buffer(session=session, result=result)
        if rendered.replace:
            output_text = rendered.text
        else:
            output_text = f"{output_text}{rendered.text}"
        set_output_text(output_text)

    def cancel_active_follow() -> None:
        nonlocal active_follow_task, active_follow_run_id
        if active_follow_task is not None:
            active_follow_task.cancel()
        active_follow_task = None
        active_follow_run_id = None

    async def follow_run_progress(
        *,
        run_id: str,
        previous_status: str = "",
    ) -> ActionResult:
        nonlocal status_text
        while True:
            progress_result = await asyncio.to_thread(
                poll_run_progress,
                session=session,
                run_id=run_id,
                runtime=runtime,
            )
            render_result = build_progress_render_result(
                result=progress_result,
                previous_status=previous_status,
            )
            if render_result is not None:
                apply_result(render_result)
            status_text = build_result_status_text(result=progress_result)
            app.invalidate()

            current_status = ""
            if progress_result.run is not None:
                current_status = progress_result.run.status.upper()
            if current_status in _RUN_PROGRESS_TERMINAL_STATUSES:
                return progress_result

            previous_status = current_status
            await asyncio.sleep(_RUN_PROGRESS_POLL_INTERVAL_SECONDS)

    def start_follow_task(
        *,
        run_id: str,
        previous_status: str = "",
    ) -> None:
        nonlocal active_follow_task, active_follow_run_id, status_text
        if not run_id:
            return

        if active_follow_run_id == run_id and active_follow_task is not None:
            if not active_follow_task.done():
                return

        cancel_active_follow()

        async def _runner() -> None:
            nonlocal active_follow_task, active_follow_run_id, status_text
            try:
                final_result = await follow_run_progress(
                    run_id=run_id,
                    previous_status=previous_status,
                )
                status_text = build_result_status_text(result=final_result)
            except asyncio.CancelledError:
                return
            finally:
                if active_follow_task is asyncio.current_task():
                    active_follow_task = None
                    active_follow_run_id = None
                app.invalidate()

        active_follow_run_id = run_id
        create_background_task = getattr(app, "create_background_task", None)
        if callable(create_background_task):
            active_follow_task = create_background_task(_runner())
            return
        active_follow_task = asyncio.create_task(_runner())

    async def process_submit_command(
        *,
        command: UiCommand,
    ) -> None:
        nonlocal status_busy, status_text
        try:
            result = await asyncio.to_thread(
                handle_command,
                session=session,
                command=command,
                runtime=runtime,
            )
            final_result = result
            render_initial_result = True

            if should_refresh_after_run(result):
                apply_result(result)
                render_initial_result = False
                start_follow_task(
                    run_id=result.run.run_id or "",
                    previous_status=result.run.status.upper(),
                )
            elif should_refresh_after_input(result) and isinstance(command, InputCommand):
                render_initial_result = False
                start_follow_task(run_id=command.run_id)

            if render_initial_result:
                apply_result(result)
            status_text = build_result_status_text(result=final_result)
            if final_result.kind == "exit":
                app.exit(result=session.session_key)
        except Exception as exc:  # noqa: BLE001
            error_result = ActionResult(kind="echo", message=f"error: {exc}")
            apply_result(error_result)
            status_text = "Error"
        finally:
            status_busy = False
            app.invalidate()

    def submit_buffer() -> None:
        nonlocal status_busy, status_text
        if status_busy:
            return

        raw_value = input_area.text
        if raw_value == "":
            return

        waiting_run = get_selected_waiting_input_run(session)
        if waiting_run is not None and not raw_value.strip():
            result = build_empty_reply_result(run=waiting_run)
            apply_result(result)
            status_text = build_result_status_text(result=result)
            app.invalidate()
            return

        command = build_submit_command(session=session, text=raw_value)
        if isinstance(command, RunCommand):
            cancel_active_follow()
        input_area.buffer.reset()
        status_busy = True
        status_text = build_pending_status_text(command=command)
        if isinstance(command, InputCommand):
            status_text = build_pending_input_status_text(run=waiting_run)
        app.invalidate()

        create_background_task = getattr(app, "create_background_task", None)
        if callable(create_background_task):
            create_background_task(
                process_submit_command(
                    command=command,
                )
            )
            return

        input_area.buffer.text = raw_value
        asyncio.run(
            process_submit_command(
                command=command,
            )
        )

    def scroll_output(*, delta: int) -> None:
        window = output_area.window
        window.vertical_scroll = max(0, window.vertical_scroll + delta)
        app.invalidate()

    def get_output_page_size() -> int:
        render_info = output_area.window.render_info
        if render_info is None:
            return 10
        return max(3, render_info.window_height - 1)

    def scroll_output_to_end() -> None:
        page_size = get_output_page_size()
        line_count = output_area.buffer.document.line_count
        output_area.window.vertical_scroll = max(0, line_count - page_size)
        app.invalidate()

    key_bindings = KeyBindings()

    @key_bindings.add("c-j")
    def _submit(_event: Any) -> None:
        submit_buffer()

    @key_bindings.add("enter")
    def _enter(_event: Any) -> None:
        if accept_completion(input_area.buffer):
            return
        if should_submit_on_enter(
            input_area.text,
            waiting_input=get_selected_waiting_input_run(session) is not None,
        ):
            submit_buffer()
            return
        input_area.buffer.insert_text("\n")

    @key_bindings.add("up")
    def _up(_event: Any) -> None:
        if has_active_completion(input_area.buffer):
            input_area.buffer.complete_previous(count=1)
            return
        input_area.buffer.cursor_up(count=1)

    @key_bindings.add("down")
    def _down(_event: Any) -> None:
        if has_active_completion(input_area.buffer):
            input_area.buffer.complete_next(count=1)
            return
        input_area.buffer.cursor_down(count=1)

    @key_bindings.add("left")
    def _left(_event: Any) -> None:
        input_area.buffer.cursor_left(count=1)

    @key_bindings.add("right")
    def _right(_event: Any) -> None:
        input_area.buffer.cursor_right(count=1)

    @key_bindings.add("pageup")
    def _page_up(_event: Any) -> None:
        scroll_output(delta=-get_output_page_size())

    @key_bindings.add("pagedown")
    def _page_down(_event: Any) -> None:
        scroll_output(delta=get_output_page_size())

    @key_bindings.add("home")
    def _home(_event: Any) -> None:
        output_area.window.vertical_scroll = 0
        app.invalidate()

    @key_bindings.add("end")
    def _end(_event: Any) -> None:
        scroll_output_to_end()

    @key_bindings.add("c-c")
    def _exit(_event: Any) -> None:
        apply_result(ActionResult(kind="exit"))
        app.exit(result=session.session_key)

    @key_bindings.add("c-l")
    def _clear_input(_event: Any) -> None:
        input_area.buffer.reset()

    content = HSplit(
        [
            Window(
                height=2,
                content=FormattedTextControl(
                    lambda: (
                        f"{build_header_title_line(session=session)}\n"
                        f"{build_header_meta_line(session=session)}"
                    )
                ),
            ),
            Window(height=1, char=" "),
            output_area,
            Window(
                height=1,
                style="class:status",
                content=FormattedTextControl(
                    lambda: build_status_fragments(
                        build_status_line(
                            session=session,
                            status_text=status_text,
                            busy=status_busy,
                        )
                    )
                ),
            ),
            input_area,
            Window(height=1, char=" "),
            Window(
                height=1,
                style="class:footer",
                content=FormattedTextControl(lambda: build_footer_line(session=session)),
            ),
        ]
    )
    layout = Layout(
        FloatContainer(
            content=VSplit(
                [
                    Window(width=1, char=" "),
                    content,
                    Window(width=1, char=" "),
                ]
            ),
            floats=[
                Float(
                    left=3,
                    ycursor=True,
                    content=CompletionsMenu(display_arrows=False),
                )
            ],
        )
    )
    style = Style.from_dict(build_prompt_toolkit_style_dict(ui_theme=theme))
    app: Application[str] = Application(
        layout=layout,
        key_bindings=key_bindings,
        full_screen=True,
        refresh_interval=0.1,
        style=style,
        cursor=CursorShape.BLINKING_BEAM,
    )
    with patch_stdout():
        return app.run()
