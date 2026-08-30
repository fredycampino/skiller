import pytest

from skiller.application.use_cases.run.bootstrap_runtime import BootstrapRuntimeUseCase
from skiller.domain.run.runtime_bootstrap_port import RuntimeBootstrapError


class _FailingRuntimeBootstrap:
    def init_db(self) -> None:
        raise RuntimeBootstrapError("Runtime storage initialization failed")


def test_bootstrap_runtime_propagates_stable_error() -> None:
    use_case = BootstrapRuntimeUseCase(store=_FailingRuntimeBootstrap())

    with pytest.raises(
        RuntimeBootstrapError,
        match="Runtime storage initialization failed",
    ):
        use_case.initialize()
