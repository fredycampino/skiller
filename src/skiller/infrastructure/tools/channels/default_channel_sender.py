import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from skiller.application.ports.channel_sender_port import ChannelSenderPort, ChannelSendResult
from skiller.infrastructure.config.settings import Settings


class DefaultChannelSender(ChannelSenderPort):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_available(
        self,
        *,
        channel: str,
    ) -> bool:
        normalized_channel = str(channel).strip().lower()
        if normalized_channel != "whatsapp":
            raise ValueError(f"Unsupported channel '{channel}'")

        endpoint = (
            f"http://{self.settings.whatsapp_bridge_host}:"
            f"{self.settings.whatsapp_bridge_port}/health"
        )
        try:
            with urlopen(endpoint, timeout=0.5) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
            return False

        if response.status != 200:
            return False
        if not isinstance(payload, dict):
            return False

        status = str(payload.get("status", "")).strip().lower()
        paired = payload.get("paired") is True
        return status == "connected" and paired

    def send_text(
        self,
        *,
        channel: str,
        key: str,
        message: str,
    ) -> ChannelSendResult:
        normalized_channel = str(channel).strip().lower()
        normalized_key = str(key).strip()
        normalized_message = str(message).strip()

        if normalized_channel != "whatsapp":
            raise ValueError(f"Unsupported channel '{channel}'")

        endpoint = (
            f"http://{self.settings.whatsapp_bridge_host}:"
            f"{self.settings.whatsapp_bridge_port}/messages"
        )
        request = Request(
            endpoint,
            data=json.dumps(
                {
                    "channel": normalized_channel,
                    "key": normalized_key,
                    "text": normalized_message,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        timeout_seconds = self.settings.whatsapp_bridge_send_timeout_seconds
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(self._http_error_message(exc)) from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError("Failed to reach WhatsApp bridge") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Invalid response from WhatsApp bridge")

        if payload.get("accepted") is not True:
            error = str(payload.get("error", "")).strip()
            raise RuntimeError(error or "WhatsApp bridge rejected send")

        raw_message_id = payload.get("message_id")
        return ChannelSendResult(
            channel=str(payload.get("channel", normalized_channel)).strip() or normalized_channel,
            key=str(payload.get("key", normalized_key)).strip() or normalized_key,
            message=normalized_message,
            message_id=(
                str(raw_message_id).strip()
                if isinstance(raw_message_id, str) and raw_message_id.strip()
                else None
            ),
        )

    def _http_error_message(self, error: HTTPError) -> str:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            payload = None

        if isinstance(payload, dict):
            message = str(payload.get("error", "")).strip()
            if message:
                return message

        return f"WhatsApp bridge request failed with status {error.code}"
