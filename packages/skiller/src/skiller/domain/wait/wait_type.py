from enum import Enum


class WaitType(str, Enum):
    INPUT = "wait_input"
    WEBHOOK = "wait_webhook"
    CHANNEL = "wait_channel"
