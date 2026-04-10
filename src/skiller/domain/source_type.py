from enum import Enum


class SourceType(str, Enum):
    INPUT = "input"
    WEBHOOK = "webhook"
    CHANNEL = "channel"
