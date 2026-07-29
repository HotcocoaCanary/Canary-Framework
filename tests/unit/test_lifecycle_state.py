"""Lifecycle state machine tests."""

import pytest

from canary_framework.common.errors import LifecycleHookError, LifecycleStateError
from canary_framework.common.types import LifecycleState
from canary_framework.core.service import ServiceBase


async def test_repeated_public_transition_is_rejected() -> None:
    subject = ServiceBase()
    await subject.init()

    with pytest.raises(LifecycleStateError, match=r"ServiceBase.init.*initialized"):
        await subject.init()


async def test_sync_extension_is_rejected_and_marks_failed() -> None:
    class Subject(ServiceBase):
        def on_init(self) -> None:
            self.called = True

    subject = Subject()
    with pytest.raises(LifecycleHookError, match=r"Subject\.on_init must be async"):
        await subject.init()

    assert subject.lifecycle_state is LifecycleState.FAILED


async def test_private_phases_run_in_order() -> None:
    events: list[str] = []

    class Subject(ServiceBase):
        async def _init(self) -> None:
            events.append("private-init")

        async def on_init(self) -> None:
            events.append("init")

        async def _startup(self) -> None:
            events.append("private-startup")

        async def on_startup(self) -> None:
            events.append("startup")

        async def on_shutdown(self) -> None:
            events.append("shutdown")

        async def _shutdown(self) -> None:
            events.append("private-shutdown")

    subject = Subject()
    await subject.init()
    await subject.startup()
    await subject.shutdown()

    assert events == [
        "private-init",
        "init",
        "private-startup",
        "startup",
        "shutdown",
        "private-shutdown",
    ]


async def test_private_rollback_is_idempotent_and_state_stays_failed() -> None:
    calls: list[str] = []

    class Subject(ServiceBase):
        async def on_shutdown(self) -> None:
            calls.append("shutdown")

    subject = Subject()
    await subject.init()
    subject._cf_state = LifecycleState.FAILED

    await subject._rollback(started=False)
    await subject._rollback(started=False)

    assert calls == ["shutdown"]
    assert subject.lifecycle_state is LifecycleState.FAILED
    with pytest.raises(LifecycleStateError):
        await subject.shutdown()


async def test_init_failure_rolls_back_and_preserves_failed_state() -> None:
    events: list[str] = []

    class Subject(ServiceBase):
        async def _init(self) -> None:
            events.append("init")
            raise RuntimeError("boom")

        async def on_shutdown(self) -> None:
            events.append("shutdown")

        async def _shutdown(self) -> None:
            events.append("cleanup")

    subject = Subject()
    with pytest.raises(RuntimeError, match="boom"):
        await subject.init()

    assert events == ["init", "shutdown", "cleanup"]
    assert subject.lifecycle_state is LifecycleState.FAILED
