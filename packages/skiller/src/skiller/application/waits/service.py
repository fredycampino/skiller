from skiller.application.use_cases.ingress.handle_channel import (
    HandleChannelInput,
    HandleChannelResult,
    HandleChannelUseCase,
)
from skiller.application.use_cases.ingress.handle_input import (
    HandleInputInput,
    HandleInputResult,
    HandleInputUseCase,
)
from skiller.application.use_cases.ingress.handle_webhook import (
    HandleWebhookInput,
    HandleWebhookResult,
    HandleWebhookUseCase,
)
from skiller.application.use_cases.query.list_webhooks import (
    ListWebhooksResult,
    ListWebhooksUseCase,
)
from skiller.application.use_cases.webhook.register_webhook import (
    RegisterWebhookInput,
    RegisterWebhookResult,
    RegisterWebhookUseCase,
)
from skiller.application.use_cases.webhook.remove_webhook import (
    RemoveWebhookResult,
    RemoveWebhookUseCase,
)


class WaitApplicationService:
    def __init__(
        self,
        handle_input_use_case: HandleInputUseCase,
        handle_channel_use_case: HandleChannelUseCase,
        handle_webhook_use_case: HandleWebhookUseCase,
        list_webhooks_use_case: ListWebhooksUseCase,
        register_webhook_use_case: RegisterWebhookUseCase,
        remove_webhook_use_case: RemoveWebhookUseCase,
    ) -> None:
        self.handle_input_use_case = handle_input_use_case
        self.handle_channel_use_case = handle_channel_use_case
        self.handle_webhook_use_case = handle_webhook_use_case
        self.list_webhooks_use_case = list_webhooks_use_case
        self.register_webhook_use_case = register_webhook_use_case
        self.remove_webhook_use_case = remove_webhook_use_case

    def handle_input(self, request: HandleInputInput) -> HandleInputResult:
        return self.handle_input_use_case.execute(request)

    def handle_channel(self, request: HandleChannelInput) -> HandleChannelResult:
        return self.handle_channel_use_case.execute(request)

    def handle_webhook(self, request: HandleWebhookInput) -> HandleWebhookResult:
        return self.handle_webhook_use_case.execute(request)

    def register_webhook(self, request: RegisterWebhookInput) -> RegisterWebhookResult:
        return self.register_webhook_use_case.execute(request)

    def list_webhooks(self) -> ListWebhooksResult:
        return self.list_webhooks_use_case.execute()

    def remove_webhook(self, webhook: str) -> RemoveWebhookResult:
        return self.remove_webhook_use_case.execute(webhook)
