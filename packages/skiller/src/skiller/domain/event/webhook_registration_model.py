from enum import StrEnum


class WebhookMethod(StrEnum):
    GET = "GET"
    POST = "POST"


class WebhookAuth(StrEnum):
    NONE = "none"
    SIGNED = "signed"


class WebhookPayloadSource(StrEnum):
    BODY_JSON = "body_json"
    QUERY = "query"
