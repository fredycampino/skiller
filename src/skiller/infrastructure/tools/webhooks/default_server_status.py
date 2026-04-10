from urllib.error import URLError
from urllib.request import urlopen

from skiller.application.ports.server_status_port import ServerStatusPort
from skiller.infrastructure.config.settings import Settings


class DefaultServerStatus(ServerStatusPort):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_available(self) -> bool:
        endpoint = (
            f"http://{self.settings.webhooks_host}:{self.settings.webhooks_port}/health"
        )
        try:
            with urlopen(endpoint, timeout=0.5) as response:  # noqa: S310
                return response.status == 200
        except (URLError, TimeoutError, ValueError):
            return False
