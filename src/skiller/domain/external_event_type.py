from enum import Enum


class ExternalEventType(str, Enum):
    INPUT = "input"
    WEBHOOK = "webhook"
