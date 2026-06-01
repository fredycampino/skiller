from __future__ import annotations

from dataclasses import dataclass, replace

from rich.console import RenderableType

from stui.di.strings import DEFAULT_TUI_STRINGS, TuiStrings
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
from stui.screen.transcript.run_finished_view import RunFinishedView
from stui.screen.transcript.run_output_view import RunOutputView
from stui.screen.transcript.run_resume_view import RunResumeView
from stui.screen.transcript.run_step_view import RunStepView
from stui.screen.transcript.run_system_notice_view import RunSystemNoticeView
from stui.screen.transcript.run_waiting_input_view import RunWaitingInputView
from stui.screen.transcript.run_waiting_webhook_view import RunWaitingWebhookView
from stui.screen.transcript.step_error_view import StepErrorView
from stui.screen.transcript.step_notify_output_view import StepNotifyOutputView
from stui.screen.transcript.step_output_view import StepOutputView
from stui.screen.transcript.step_shell_output_view import StepShellOutputView
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
    RunFinishedItem,
    RunOutputItem,
    RunResumeItem,
    RunStepItem,
    RunSyncSnapshotItem,
    RunWaitingInputItem,
    RunWaitingWebhookItem,
    StepErrorItem,
    StepNotifyOutputItem,
    StepOutputItem,
    StepShellOutputItem,
    TranscriptItem,
    TranscriptMode,
    UserInputItem,
)


@dataclass(frozen=True)
class RenderTranscript:
    strings: TuiStrings = DEFAULT_TUI_STRINGS

    def render(
        self,
        *,
        items: list[TranscriptItem],
        mode: TranscriptMode = TranscriptMode.CHAT,
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
        views = self._active_step_output(views=views)
        views = self._active_notify(views=views)
        views = self._active_webhook_wait(views=views)
        views = self._active_tool(views=views)
        renderables: list[RenderableType] = []
        for view in views:
            renderables.append(view.render(theme=theme))
        return renderables

    def _active_webhook_wait(
        self,
        *,
        views: list[TranscriptView],
    ) -> list[TranscriptView]:
        if not views:
            return views

        latest_index = len(views) - 1
        active_views: list[TranscriptView] = []
        for index, view in enumerate(views):
            if isinstance(view, RunWaitingWebhookView):
                muted = index != latest_index
                active_views.append(
                    RunWaitingWebhookView(
                        item=replace(view.item, muted=muted),
                        strings=view.strings,
                    )
                )
                continue
            active_views.append(view)
        return active_views

    def _active_step_output(
        self,
        *,
        views: list[TranscriptView],
    ) -> list[TranscriptView]:
        if not views:
            return views

        latest_index = self._active_output_index(views=views)
        if latest_index is None:
            return views
        latest_is_step_output = isinstance(
            views[latest_index],
            (StepOutputView, StepShellOutputView),
        )
        active_views: list[TranscriptView] = []
        for index, view in enumerate(views):
            if isinstance(view, StepOutputView):
                muted = not (latest_is_step_output and index == latest_index)
                active_views.append(
                    StepOutputView(item=replace(view.item, muted=muted))
                )
                continue
            if isinstance(view, StepShellOutputView):
                muted = not (latest_is_step_output and index == latest_index)
                active_views.append(
                    StepShellOutputView(item=replace(view.item, muted=muted))
                )
                continue
            active_views.append(view)
        return active_views

    def _active_notify(
        self,
        *,
        views: list[TranscriptView],
    ) -> list[TranscriptView]:
        if not views:
            return views

        latest_index = self._active_output_index(views=views)
        if latest_index is None:
            return views
        latest_is_notify = isinstance(views[latest_index], StepNotifyOutputView)
        active_views: list[TranscriptView] = []
        for index, view in enumerate(views):
            if isinstance(view, StepNotifyOutputView):
                muted = not (latest_is_notify and index == latest_index)
                active_views.append(
                    StepNotifyOutputView(item=replace(view.item, muted=muted))
                )
                continue
            active_views.append(view)
        return active_views

    def _active_output_index(
        self,
        *,
        views: list[TranscriptView],
    ) -> int | None:
        if not views:
            return None
        latest_index = len(views) - 1
        if isinstance(views[latest_index], RunWaitingInputView):
            latest_index -= 1
        if latest_index < 0:
            return None
        return latest_index

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
        views: list[TranscriptView] = [IntroView(strings=self.strings)]
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
        if isinstance(item, RunSyncSnapshotItem):
            return RunSystemNoticeView(item=item, strings=self.strings)
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
        if isinstance(item, StepErrorItem):
            return StepErrorView(item=item)
        if isinstance(item, StepNotifyOutputItem):
            return StepNotifyOutputView(item=item)
        if isinstance(item, StepOutputItem):
            return StepOutputView(item=item)
        if isinstance(item, StepShellOutputItem):
            return StepShellOutputView(item=item)
        if isinstance(item, RunOutputItem):
            return RunOutputView(item=item)
        if isinstance(item, RunFinishedItem):
            return RunFinishedView(item=item)
        if isinstance(item, RunWaitingInputItem):
            return RunWaitingInputView(item=item)
        if isinstance(item, RunWaitingWebhookItem):
            return RunWaitingWebhookView(item=item, strings=self.strings)
        return InfoView(item=InfoItem(text=""))
