from skiller.application.use_cases.run.check_webhook_wait import WebhookWaitConflict


class WebhookWaitConflictError(ValueError):
    def __init__(self, conflict: WebhookWaitConflict) -> None:
        self.conflict = conflict
        super().__init__(
            f"Webhook '{conflict.webhook}:{conflict.key}' is already being waited "
            f"by run '{conflict.run_id}'. Delete it with "
            f"'skiller delete {conflict.run_id}' or wait for it to finish."
        )
