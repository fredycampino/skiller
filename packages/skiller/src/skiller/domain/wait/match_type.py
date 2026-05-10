from enum import Enum


class MatchType(str, Enum):
    RUN = "run"
    SIGNAL = "signal"
    CHANNEL_KEY = "channel_key"
