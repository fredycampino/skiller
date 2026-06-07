from skiller.application.action.action_uid_factory import ActionUidFactory
from skiller.domain.action.action_model import Action, ActionType, OpenUrlAction, RunAction


class ActionMapper:
    def __init__(self, uid_factory: ActionUidFactory) -> None:
        self.uid_factory = uid_factory

    def to_notify_action(
        self,
        *,
        step_id: str,
        value: object,
        default_message: str,
    ) -> Action | None:
        if value is None:
            return None

        if not isinstance(value, dict):
            raise ValueError(f"Notify step '{step_id}' action must be an object")

        raw_type = value.get("type")
        if not isinstance(raw_type, str):
            raise ValueError(f"Notify step '{step_id}' action type must be string")
        try:
            action_type = ActionType(raw_type.strip())
        except ValueError as exc:
            raise ValueError(
                f"Notify step '{step_id}' action type must be "
                f"'{ActionType.OPEN_URL.value}' or '{ActionType.RUN.value}'"
            ) from exc

        if action_type == ActionType.OPEN_URL:
            return self.to_open_url_action(
                step_id=step_id,
                value=value,
                default_message=default_message,
            )

        return self.to_run_action(step_id=step_id, value=value)

    def to_open_url_action(
        self,
        *,
        step_id: str,
        value: dict[object, object],
        default_message: str,
    ) -> OpenUrlAction:
        raw_label = value.get("label")
        if not isinstance(raw_label, str):
            raise ValueError(f"Notify step '{step_id}' action label must be string")
        label = raw_label.strip()
        if not label:
            raise ValueError(f"Notify step '{step_id}' action requires non-empty label")

        raw_message = value.get("message")
        if raw_message is not None and not isinstance(raw_message, str):
            raise ValueError(f"Notify step '{step_id}' action message must be string")
        message = raw_message.strip() if raw_message is not None else ""
        if not message:
            message = default_message

        raw_url = value.get("url")
        if not isinstance(raw_url, str):
            raise ValueError(f"Notify step '{step_id}' action url must be string")
        url = raw_url.strip()
        if not _is_http_url(url):
            raise ValueError(f"Notify step '{step_id}' action requires http(s) url")

        raw_auto = value.get("auto", False)
        if not isinstance(raw_auto, bool):
            raise ValueError(f"Notify step '{step_id}' action auto must be boolean")

        return OpenUrlAction(
            uid=self.uid_factory.new_uid(),
            label=label,
            message=message,
            url=url,
            auto=raw_auto,
        )

    def to_run_action(
        self,
        *,
        step_id: str,
        value: dict[object, object],
    ) -> RunAction:
        raw_label = value.get("label")
        if not isinstance(raw_label, str):
            raise ValueError(f"Notify step '{step_id}' action label must be string")
        label = raw_label.strip()
        if not label:
            raise ValueError(f"Notify step '{step_id}' action requires non-empty label")

        raw_arg = value.get("arg")
        if not isinstance(raw_arg, str):
            raise ValueError(f"Notify step '{step_id}' run action arg must be string")
        arg = raw_arg.strip()
        if not arg:
            raise ValueError(f"Notify step '{step_id}' run action requires non-empty arg")

        raw_params = value.get("params")
        if raw_params is not None and not isinstance(raw_params, str):
            raise ValueError(f"Notify step '{step_id}' run action params must be string")

        raw_auto = value.get("auto", False)
        if not isinstance(raw_auto, bool):
            raise ValueError(f"Notify step '{step_id}' action auto must be boolean")

        return RunAction(
            uid=self.uid_factory.new_uid(),
            label=label,
            arg=arg,
            params=raw_params,
            auto=raw_auto,
        )


def _is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))
