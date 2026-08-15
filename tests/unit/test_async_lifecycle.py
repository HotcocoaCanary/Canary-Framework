"""Unit tests for async hooks and the sync/async mix."""

import pytest

from canary_framework import (
    Canary,
    LifecycleState,
    cocoa,
    on_init,
    on_start,
    on_stop,
)

pytestmark = pytest.mark.unit


async def test_async_context_awaits_all_phases_in_order() -> None:
    events: list[str] = []

    @cocoa
    class Service:
        @on_init
        async def prepare(self) -> None:
            events.append("prepare")

        @on_start
        async def connect(self) -> None:
            events.append("connect")

        @on_stop
        async def disconnect(self) -> None:
            events.append("disconnect")

    async with Canary(Service) as canary:
        assert canary.state is LifecycleState.STARTED
        assert events == ["prepare", "connect"]

    assert canary.state is LifecycleState.STOPPED
    assert events == ["prepare", "connect", "disconnect"]


async def test_mixed_sync_and_async_hooks_run_in_order() -> None:
    calls: list[str] = []

    @cocoa
    class Service:
        @on_start
        async def async_hook(self) -> None:
            calls.append("async")

        @on_start
        def sync_hook(self) -> None:
            calls.append("sync")

    async with Canary(Service):
        pass

    # 同一阶段里 sync 与 async 钩子按定义序都执行，互不干扰。
    assert calls == ["async", "sync"]


async def test_manual_methods_transition_state() -> None:
    @cocoa
    class Service:
        pass

    canary = Canary(Service)
    assert canary.state is LifecycleState.NEW

    await canary.init()
    assert canary.state is LifecycleState.INITIALIZED

    await canary.start()
    assert canary.state is LifecycleState.STARTED

    await canary.stop()
    assert canary.state is LifecycleState.STOPPED


async def test_async_hook_failure_marks_failed_and_propagates() -> None:
    @cocoa
    class Service:
        @on_start
        async def connect(self) -> None:
            raise RuntimeError("connect exploded")

    canary = Canary(Service)
    await canary.init()
    with pytest.raises(RuntimeError, match="connect exploded"):
        await canary.start()
    assert canary.state is LifecycleState.FAILED


async def test_async_exit_runs_stop_and_propagates_body_exception() -> None:
    stopped: list[str] = []

    @cocoa
    class Service:
        @on_stop
        async def disconnect(self) -> None:
            stopped.append("disconnect")

    with pytest.raises(RuntimeError, match="boom"):
        async with Canary(Service):
            raise RuntimeError("boom")

    assert stopped == ["disconnect"]


async def test_deps_injected_before_async_start_hook() -> None:
    @cocoa
    class Config:
        pass

    seen: list[object] = []

    @cocoa(deps=[Config])
    class Database:
        @on_start
        async def connect(self) -> None:
            seen.append(self.config)  # 依赖在钩子执行前已注入

    async with Canary(Database) as canary:
        assert seen == [canary[Config]]
