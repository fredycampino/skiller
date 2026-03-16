import uvicorn

from skiller.infrastructure.config.settings import get_settings


def main() -> None:
    """Webhook process entrypoint."""
    settings = get_settings()
    uvicorn.run(
        "skiller.tools.webhooks.app:create_app",
        factory=True,
        host=settings.webhooks_host,
        port=settings.webhooks_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
