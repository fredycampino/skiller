from __future__ import annotations

import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field

from stui.adapter.cli_notify_action_adapter import CliNotifyActionAdapter
from stui.port.notify_action_port import NotifyActionAck, NotifyActionAckStatus


@dataclass
class DefaultNotifyActionPort:
    command_adapter: CliNotifyActionAdapter = field(default_factory=CliNotifyActionAdapter)
    url_opener: Callable[[str], bool] = webbrowser.open

    def open(self, *, run_id: str, action_uid: str, url: str) -> NotifyActionAck:
        normalized_run_id = run_id.strip()
        normalized_action_uid = action_uid.strip()
        normalized_url = url.strip()
        if not normalized_run_id:
            return NotifyActionAck(
                status=NotifyActionAckStatus.REJECTED,
                run_id="",
                action_uid=normalized_action_uid,
                message="error: run_id is required",
            )
        if not normalized_action_uid:
            return NotifyActionAck(
                status=NotifyActionAckStatus.REJECTED,
                run_id=normalized_run_id,
                action_uid="",
                message="error: action_uid is required",
            )
        if not normalized_url:
            return NotifyActionAck(
                status=NotifyActionAckStatus.REJECTED,
                run_id=normalized_run_id,
                action_uid=normalized_action_uid,
                message="error: url is required",
            )

        opened = self.url_opener(normalized_url)
        if opened:
            return NotifyActionAck(
                status=NotifyActionAckStatus.ACCEPTED,
                run_id=normalized_run_id,
                action_uid=normalized_action_uid,
            )
        return NotifyActionAck(
            status=NotifyActionAckStatus.ERROR,
            run_id=normalized_run_id,
            action_uid=normalized_action_uid,
            message="error: could not open url",
        )

    def done(self, *, run_id: str, action_uid: str) -> NotifyActionAck:
        return self.command_adapter.done(run_id=run_id, action_uid=action_uid)
