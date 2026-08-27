from dataclasses import dataclass
from enum import StrEnum


class WebhookMethod(StrEnum):
    GET = "GET"
    POST = "POST"


class WebhookAuth(StrEnum):
    NONE = "none"
    SIGNED = "signed"
    TOKEN = "token"


class WebhookPayloadSource(StrEnum):
    BODY_JSON = "body_json"
    QUERY = "query"


@dataclass(frozen=True)
class WebhookRegistration:
    webhook: str
    secret: str
    method: WebhookMethod
    auth: WebhookAuth
    payload_source: WebhookPayloadSource
    enabled: bool
    created_at: str | None = None
    token_header: str | None = None

    def __post_init__(self) -> None:
        if self.auth == WebhookAuth.TOKEN and self.token_header is None:
            raise ValueError("token authentication requires token_header")
        if self.auth != WebhookAuth.TOKEN and self.token_header is not None:
            raise ValueError("token_header is only supported with token authentication")
