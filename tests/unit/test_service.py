"""Unit tests for the lifecycle-only ServiceBase."""

from canary_framework.common.types import LifecycleState
from canary_framework.core.service import ServiceBase


def test_plain_service_exposes_no_http_surface() -> None:
    subject = ServiceBase()
    assert not callable(subject)
    assert not hasattr(subject, "asgi_app")
    assert not hasattr(subject, "openapi")
    assert not hasattr(subject, "router")
    assert subject.lifecycle_state is LifecycleState.CREATED


async def test_lifecycle_template_calls_async_extensions_in_order() -> None:
    events: list[str] = []

    class Subject(ServiceBase):
        async def on_init(self) -> None:
            events.append("init")

        async def on_startup(self) -> None:
            events.append("startup")

        async def on_shutdown(self) -> None:
            events.append("shutdown")

    subject = Subject()
    await subject.init()
    await subject.startup()
    await subject.shutdown()

    assert events == ["init", "startup", "shutdown"]
    assert subject.lifecycle_state is LifecycleState.STOPPED
