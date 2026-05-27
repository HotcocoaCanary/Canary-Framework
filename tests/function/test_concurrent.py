"""Concurrent and stress tests for Canary Framework.

Tests:
    - Multiple independent Canary instances running in parallel
    - Race conditions and state isolation
    - Repeated lifecycle cycling
    - Error propagation from async hooks
    - Lifecycle guard checks (init/start/stop without config)
"""

from __future__ import annotations

import asyncio
import time

import pytest

from canary_framework import Canary, module, on_config, on_end, on_init, on_start, service
from canary_framework.common.exceptions import CanaryFrameworkError, LifecycleHookError


@pytest.mark.functional
class TestConcurrentCanaryInstances:
    """Multiple independent Canary instances should coexist without interference."""

    async def test_parallel_independent_canaries(self) -> None:
        """Launch 10 Canary instances in parallel — no shared state conflict."""
        results: list[str] = []

        async def launch(name: str) -> None:
            @service(name)
            class Svc:
                @on_start
                async def start(self) -> None:
                    await asyncio.sleep(0.01)
                    results.append(name)

            app = Canary(Svc)
            await app.config()
            await app.init()
            await app.start()

        await asyncio.gather(*(launch(f"svc-{i}") for i in range(10)))
        assert len(results) == 10
        assert sorted(results) == sorted(f"svc-{i}" for i in range(10))

    async def test_parallel_canaries_with_deps(self) -> None:
        """Multiple Canary instances with dependency graphs run in parallel."""

        async def build_and_run(seed: int) -> list[str]:
            calls: list[str] = []

            @service(f"a-{seed}")
            class A:
                @on_start
                def start(self) -> None:
                    calls.append(f"a-{seed}")

            @service(f"b-{seed}", deps=[A])
            class B:
                @on_start
                def start(self) -> None:
                    calls.append(f"b-{seed}")

            @module(f"m-{seed}", services=[A, B])
            class M:
                pass

            app = Canary(M)
            await app.config()
            await app.init()
            await app.start()
            return calls

        tasks = [build_and_run(i) for i in range(5)]
        all_calls = await asyncio.gather(*tasks)

        for seed in range(5):
            seed_calls = all_calls[seed]
            assert f"a-{seed}" in seed_calls
            assert f"b-{seed}" in seed_calls
            assert seed_calls.index(f"a-{seed}") < seed_calls.index(f"b-{seed}")

    async def test_parallel_canaries_isolated_registries(self) -> None:
        """Registry is per-Canary — instances should not leak between Canary instances."""

        @service("shared-name")
        class SvcA:
            pass

        @service("shared-name")
        class SvcB:
            pass

        app_a = Canary(SvcA)
        app_b = Canary(SvcB)

        await app_a.config()
        await app_b.config()

        assert len(app_a.registry) == 1
        assert len(app_b.registry) == 1
        assert app_a.registry.get_by_name("shared-name").cls is SvcA
        assert app_b.registry.get_by_name("shared-name").cls is SvcB


@pytest.mark.functional
class TestConcurrentAsyncHooks:
    """Async hook execution correctness under various timing conditions."""

    async def test_many_async_hooks_run_completely(self) -> None:
        """Each async hook must finish before the next one starts (sequential topo order)."""
        log: list[str] = []

        @service("s1")
        class S1:
            @on_init
            async def init(self) -> None:
                await asyncio.sleep(0.02)
                log.append("s1:init")

            @on_start
            async def start(self) -> None:
                await asyncio.sleep(0.01)
                log.append("s1:start")

        @service("s2")
        class S2:
            @on_init
            async def init(self) -> None:
                await asyncio.sleep(0.01)
                log.append("s2:init")

            @on_start
            async def start(self) -> None:
                log.append("s2:start")

        @module("m", services=[S1, S2])
        class M:
            pass

        app = Canary(M)
        await app.config()
        await app.init()
        await app.start()

        assert log == ["s1:init", "s2:init", "s1:start", "s2:start"]

    async def test_async_hook_errors_are_propagated(self) -> None:
        """Async hook that raises should produce LifecycleHookError wrapping the cause."""

        @service("crash")
        class Crash:
            @on_init
            async def init(self) -> None:
                await asyncio.sleep(0.001)
                raise RuntimeError("async boom")

        app = Canary(Crash)
        await app.config()
        with pytest.raises(LifecycleHookError, match="async boom"):
            await app.init()

    async def test_sync_hook_errors_are_propagated(self) -> None:
        """Sync hook errors also wrapped in LifecycleHookError."""

        @service("crash-sync")
        class CrashSync:
            @on_start
            def start(self) -> None:
                raise ValueError("sync boom")

        app = Canary(CrashSync)
        await app.config()
        await app.init()
        with pytest.raises(LifecycleHookError, match="sync boom"):
            await app.start()

    async def test_concurrent_hooks_maintain_topological_order(self) -> None:
        """Sequential hooks with interleaved sleeps confirm execution order integrity."""
        timeline: list[str] = []
        timestamps: dict[str, float] = {}

        @service("slow")
        class Slow:
            @on_init
            async def init(self) -> None:
                timeline.append("slow:init-start")
                timestamps["slow:init-start"] = time.monotonic()
                await asyncio.sleep(0.05)
                timeline.append("slow:init-done")
                timestamps["slow:init-done"] = time.monotonic()

        @service("fast", deps=[Slow])
        class Fast:
            @on_init
            async def init(self) -> None:
                timeline.append("fast:init-start")
                timestamps["fast:init-start"] = time.monotonic()

        @module("mod", services=[Slow, Fast])
        class Mod:
            pass

        app = Canary(Mod)
        await app.config()
        await app.init()

        assert timestamps["slow:init-done"] < timestamps["fast:init-start"], (
            "Dependant started before dependency finished"
        )


@pytest.mark.functional
class TestLifecycleGuards:
    """Verify lifecycle phase guards prevent misuse."""

    async def test_init_without_config_raises(self) -> None:
        @service("no-config")
        class Svc:
            pass

        app = Canary(Svc)
        with pytest.raises(RuntimeError, match="before config"):
            await app.init()

    async def test_start_without_config_raises(self) -> None:
        @service("no-config")
        class Svc:
            pass

        app = Canary(Svc)
        with pytest.raises(RuntimeError, match="before config"):
            await app.start()

    async def test_stop_without_config_raises(self) -> None:
        @service("no-config")
        class Svc:
            pass

        app = Canary(Svc)
        with pytest.raises(RuntimeError, match="before config"):
            await app.stop()

    async def test_config_twice_reinitializes(self) -> None:
        """Calling config() twice re-instantiates services and re-runs hooks."""
        config_count = 0

        @service("double")
        class Double:
            @on_config
            def setup(self) -> None:
                nonlocal config_count
                config_count += 1

        app = Canary(Double)
        await app.config()
        assert config_count == 1
        await app.config()
        assert config_count == 2
        await app.init()
        await app.start()

    async def test_lifecycle_error_is_canary_framework_error(self) -> None:
        @service("broken")
        class Broken:
            @on_init
            def init(self) -> None:
                raise RuntimeError("fail")

        app = Canary(Broken)
        await app.config()
        with pytest.raises(CanaryFrameworkError):
            await app.init()


@pytest.mark.functional
class TestRepeatedCycling:
    """Start / stop cycling should work repeatedly."""

    async def test_start_stop_many_cycles(self) -> None:
        start_count = 0
        stop_count = 0

        @service("cycler")
        class Cycler:
            @on_start
            def start(self) -> None:
                nonlocal start_count
                start_count += 1

            @on_end
            def end(self) -> None:
                nonlocal stop_count
                stop_count += 1

        app = Canary(Cycler)
        await app.config()
        await app.init()

        for _ in range(5):
            await app.start()
            await app.stop()

        assert start_count == 5
        assert stop_count == 5

    async def test_stop_called_multiple_times_is_idempotent_for_hooks(self) -> None:
        """Calling stop() multiple times fires hooks each time (no guard)."""
        stop_count = 0

        @service("stopper")
        class Stopper:
            @on_end
            def end(self) -> None:
                nonlocal stop_count
                stop_count += 1

        app = Canary(Stopper)
        await app.config()
        await app.init()
        await app.start()

        await app.stop()
        await app.stop()
        await app.stop()

        assert stop_count == 3
