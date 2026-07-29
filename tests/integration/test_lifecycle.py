"""Integration tests for the lifecycle template."""

import pytest

from canary_framework.common.errors import LifecycleHookError
from canary_framework.common.types import LifecycleState
from canary_framework.core.service import ServiceBase


@pytest.mark.integration
async def test_parent_service_private_lifecycle_order() -> None:
    events: list[str] = []

    class Parent(ServiceBase):
        async def _init(self) -> None:
            events.append("parent-init")

        async def _startup(self) -> None:
            events.append("parent-startup")

        async def _shutdown(self) -> None:
            events.append("parent-shutdown")

    parent = Parent()
    await parent.init()
    await parent.startup()
    await parent.shutdown()

    assert events == ["parent-init", "parent-startup", "parent-shutdown"]
    assert parent.lifecycle_state is LifecycleState.STOPPED


@pytest.mark.integration
async def test_parent_extension_failure_is_wrapped() -> None:
    class Parent(ServiceBase):
        async def on_startup(self) -> None:
            raise ValueError("startup failed")

    parent = Parent()
    await parent.init()

    with pytest.raises(LifecycleHookError, match=r"Parent\.on_startup failed: startup failed"):
        await parent.startup()

    assert parent.lifecycle_state is LifecycleState.FAILED
