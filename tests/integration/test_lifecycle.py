"""Integration tests for dependency-engine lifecycle orchestration."""

import pytest

from canary_framework.common.errors import LifecycleHookError
from canary_framework.common.types import (
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    LifecycleState,
    ServiceMeta,
)
from canary_framework.core.service import ServiceBase
from canary_framework.engine.container import DependencyEngine


def _service(cls: type) -> type:
    setattr(cls, CF_SERVICE_MARKER, True)
    setattr(cls, CF_SERVICE_META, ServiceMeta(name=cls.__name__))
    return cls


@pytest.mark.integration
async def test_service_lifecycle_state_machine_remains_usable() -> None:
    events: list[str] = []

    class Parent(ServiceBase):
        async def _init(self) -> None:
            events.append("init")

        async def _startup(self) -> None:
            events.append("startup")

        async def _shutdown(self) -> None:
            events.append("shutdown")

    parent = Parent()
    await parent.init()
    await parent.startup()
    await parent.shutdown()

    assert events == ["init", "startup", "shutdown"]
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


class _Node:
    should_fail_init = False
    should_fail_start = False
    events: list[str]

    def __init__(self) -> None:
        self.lifecycle_state = LifecycleState.CREATED
        self._cf_parent_registry = None
        self._cf_config = None

    async def init(self) -> None:
        self.events.append(f"{type(self).__name__}-init")
        if self.should_fail_init:
            raise RuntimeError("init failed")
        self.lifecycle_state = LifecycleState.INITIALIZED

    async def startup(self) -> None:
        self.events.append(f"{type(self).__name__}-startup")
        if self.should_fail_start:
            raise RuntimeError("startup failed")
        self.lifecycle_state = LifecycleState.STARTED

    async def shutdown(self) -> None:
        self.events.append(f"{type(self).__name__}-shutdown")
        self.lifecycle_state = LifecycleState.STOPPED

    async def _rollback(self, *, started: bool) -> None:
        self.events.append(f"{type(self).__name__}-rollback-{started}")
        self.lifecycle_state = LifecycleState.STOPPED


@pytest.mark.integration
async def test_init_failure_rolls_back_only_successful_nodes_in_reverse_order() -> None:
    events: list[str] = []

    @_service
    class First(_Node):
        pass

    @_service
    class Failing(_Node):
        should_fail_init = True

    First.events = events
    Failing.events = events
    engine = DependencyEngine(children=(First, Failing), parent_registry=None, config=None)

    with pytest.raises(RuntimeError, match="init failed"):
        await engine.init()

    assert events == [
        "First-init",
        "Failing-init",
        "First-rollback-False",
    ]


@pytest.mark.integration
async def test_startup_failure_rolls_back_started_nodes_only_in_reverse_order() -> None:
    events: list[str] = []

    @_service
    class First(_Node):
        pass

    @_service
    class Failing(_Node):
        should_fail_start = True

    @_service
    class NeverStarted(_Node):
        pass

    for cls in (First, Failing, NeverStarted):
        cls.events = events
    engine = DependencyEngine(
        children=(First, Failing, NeverStarted), parent_registry=None, config=None
    )
    await engine.init()

    with pytest.raises(RuntimeError, match="startup failed"):
        await engine.startup()

    assert events == [
        "First-init",
        "Failing-init",
        "NeverStarted-init",
        "First-startup",
        "Failing-startup",
        "First-rollback-True",
    ]
