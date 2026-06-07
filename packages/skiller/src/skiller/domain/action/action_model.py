from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, TypeAlias


class ActionType(StrEnum):
    OPEN_URL = "open_url"
    RUN = "run"


class ActionStatus(StrEnum):
    DONE = "done"


class EndActionTrigger(StrEnum):
    ON_SUCCESS = "on_success"
    ON_ERROR = "on_error"


@dataclass(frozen=True, kw_only=True)
class ActionBase:
    type: ClassVar[ActionType]
    uid: str
    label: str
    auto: bool = False


@dataclass(frozen=True, kw_only=True)
class OpenUrlAction(ActionBase):
    type = ActionType.OPEN_URL
    url: str
    message: str | None = None


@dataclass(frozen=True, kw_only=True)
class RunAction(ActionBase):
    type = ActionType.RUN
    arg: str
    params: str | None = None


Action: TypeAlias = OpenUrlAction | RunAction


def action_to_public_dict(action: Action) -> dict[str, Any]:
    if isinstance(action, OpenUrlAction):
        payload = {
            "uid": action.uid,
            "type": action.type.value,
            "label": action.label,
        }
        if action.message is not None:
            payload["message"] = action.message
        payload["url"] = action.url
        payload["auto"] = action.auto
        return payload
    payload = {
        "uid": action.uid,
        "type": action.type.value,
        "label": action.label,
        "arg": action.arg,
        "auto": action.auto,
    }
    if action.params is not None:
        payload["params"] = action.params
    return payload


def action_from_dict(value: dict[str, Any]) -> Action:
    raw_uid = value.get("uid")
    if not isinstance(raw_uid, str) or not raw_uid.strip():
        raise ValueError("action uid must be non-empty string")
    uid = raw_uid.strip()

    kind = ActionType(str(value.get("type", "")))
    raw_label = value.get("label")
    if not isinstance(raw_label, str) or not raw_label.strip():
        raise ValueError("action label must be non-empty string")

    raw_auto = value.get("auto", False)
    if not isinstance(raw_auto, bool):
        raise ValueError("action auto must be boolean")

    if kind == ActionType.OPEN_URL:
        raw_message = value.get("message")
        if raw_message is not None and not isinstance(raw_message, str):
            raise ValueError("open_url action message must be string")
        raw_url = value.get("url")
        if not isinstance(raw_url, str) or not raw_url.strip():
            raise ValueError("open_url action url must be non-empty string")
        return OpenUrlAction(
            uid=uid,
            label=raw_label.strip(),
            message=raw_message,
            url=raw_url.strip(),
            auto=raw_auto,
        )

    raw_arg = value.get("arg")
    if not isinstance(raw_arg, str) or not raw_arg.strip():
        raise ValueError("run action arg must be non-empty string")
    raw_params = value.get("params")
    if raw_params is not None and not isinstance(raw_params, str):
        raise ValueError("run action params must be string")
    return RunAction(
        uid=uid,
        label=raw_label.strip(),
        arg=raw_arg.strip(),
        params=raw_params,
        auto=raw_auto,
    )
