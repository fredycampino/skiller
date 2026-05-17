from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType

from stui.screen.theme import DEFAULT_TUI_THEME, TuiTheme
from stui.screen.transcript.agent_assistant_message_view import AgentAssistantMessageView
from stui.screen.transcript.agent_final_assistant_message_view import (
    AgentFinalAssistantMessageView,
)
from stui.screen.transcript.agent_step_final_output_view import AgentStepFinalOutputView
from stui.screen.transcript.agent_system_notice_view import AgentSystemNoticeView
from stui.screen.transcript.agent_tool_call_view import AgentToolCallView
from stui.screen.transcript.agent_tool_result_view import AgentToolResultView
from stui.screen.transcript.base import TranscriptView
from stui.screen.transcript.dispatch_error_view import DispatchErrorView
from stui.screen.transcript.info_view import InfoView
from stui.screen.transcript.intro_view import IntroView
from stui.screen.transcript.run_ack_view import RunAckView
from stui.screen.transcript.run_output_view import RunOutputView
from stui.screen.transcript.run_resume_view import RunResumeView
from stui.screen.transcript.run_status_view import RunStatusView
from stui.screen.transcript.run_step_view import RunStepView
from stui.screen.transcript.run_waiting_input_view import RunWaitingInputView
from stui.screen.transcript.user_input_view import UserInputView
from stui.viewmodel.console_screen_state import (
    AgentAssistantMessageItem,
    AgentFinalAssistantMessageItem,
    AgentStepFinalOutputItem,
    AgentSystemNoticeItem,
    AgentToolCallItem,
    AgentToolResultItem,
    DispatchErrorItem,
    InfoItem,
    RunAckItem,
    RunOutputItem,
    RunResumeItem,
    RunStatusItem,
    RunStepItem,
    RunWaitingInputItem,
    TranscriptItem,
    TranscriptMode,
    UserInputItem,
)


@dataclass(frozen=True)
class RenderTranscript:
    def render(
        self,
        *,
        items: list[TranscriptItem],
        mode: TranscriptMode = TranscriptMode.FLOW,
        theme: TuiTheme = DEFAULT_TUI_THEME,
        prompt_placeholder: str | None = None,
    ) -> list[RenderableType]:
        _ = mode
        return self._render_chat(
            items=items,
            theme=theme,
            prompt_placeholder=prompt_placeholder,
        )

    def _render_chat(
        self,
        *,
        items: list[TranscriptItem],
        theme: TuiTheme,
        prompt_placeholder: str | None,
    ) -> list[RenderableType]:
        _ = prompt_placeholder
        views = self._map_chat_views(items=items)
        views = self._active_tool(views=views)
        renderables: list[RenderableType] = []
        for view in views:
            renderables.append(view.render(theme=theme))
        return renderables

    def _active_tool(
        self,
        *,
        views: list[TranscriptView],
    ) -> list[TranscriptView]:
        if not views:
            return views
        active_index = self._active_tool_index(views=views)
        if active_index is None:
            return views
        active_view = views[active_index]
        if not isinstance(active_view, AgentToolCallView):
            return views
        return [
            *views[:active_index],
            AgentToolCallView(
                item=active_view.item,
                active=True,
            ),
            *views[active_index + 1 :],
        ]

    def _active_tool_index(
        self,
        *,
        views: list[TranscriptView],
    ) -> int | None:
        index = len(views) - 1
        while index >= 0:
            view = views[index]
            if isinstance(view, AgentToolResultView):
                index -= 1
                continue
            if isinstance(view, AgentToolCallView):
                return index
            return None
        return None

    def _map_chat_views(
        self,
        *,
        items: list[TranscriptItem],
    ) -> list[TranscriptView]:
        views: list[TranscriptView] = [IntroView()]
        for item in items:
            views.append(self._to_chat_view(item=item))
        return views

    def _to_chat_view(
        self,
        *,
        item: TranscriptItem,
    ) -> TranscriptView:
        if isinstance(item, UserInputItem):
            return UserInputView(item=item)
        if isinstance(item, InfoItem):
            return InfoView(item=item)
        if isinstance(item, DispatchErrorItem):
            return DispatchErrorView(item=item)
        if isinstance(item, RunAckItem):
            return RunAckView(item=item)
        if isinstance(item, RunResumeItem):
            return RunResumeView(item=item)
        if isinstance(item, RunStepItem):
            return RunStepView(item=item, mode=TranscriptMode.CHAT)
        if isinstance(item, AgentToolCallItem):
            return AgentToolCallView(item=item)
        if isinstance(item, AgentToolResultItem):
            return AgentToolResultView(item=item)
        if isinstance(item, AgentAssistantMessageItem):
            return AgentAssistantMessageView(item=item)
        if isinstance(item, AgentFinalAssistantMessageItem):
            return AgentFinalAssistantMessageView(item=item)
        if isinstance(item, AgentStepFinalOutputItem):
            return AgentStepFinalOutputView(item=item)
        if isinstance(item, AgentSystemNoticeItem):
            return AgentSystemNoticeView(item=item)
        if isinstance(item, RunOutputItem):
            return RunOutputView(item=item)
        if isinstance(item, RunStatusItem):
            return RunStatusView(item=item)
        if isinstance(item, RunWaitingInputItem):
            return RunWaitingInputView(item=item)
        return InfoView(item=InfoItem(text=""))
