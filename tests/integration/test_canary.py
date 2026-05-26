"""Tests for the Canary core engine life-cycle."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from canary_framework.common.exceptions import CanaryFrameworkError, LifecycleHookError
from canary_framework.core import (
    Canary,
    module,
    on_end,
    on_init,
    on_start,
    service,
)
from canary_framework.core.container.registry import Registry


@pytest.mark.integration
class TestCanaryLifecycle:
    """End-to-end life-cycle tests."""

    async def test_init_start_stop_flow(self) -> None:
        calls: list[str] = []

        @service("hello")
        class Hello:
            @on_init
            def init(self) -> None:
                calls.append("init")

            @on_start
            def start(self) -> None:
                calls.append("start")

            @on_end
            def stop(self) -> None:
                calls.append("stop")

        app = Canary(Hello)
        await app.config()
        await app.init()
        await app.start()
        await app.stop()

        assert calls == ["init", "start", "stop"]

    async def test_topological_startup_order(self) -> None:
        calls: list[str] = []

        @service("a")
        class A:
            @on_init
            def init(self) -> None:
                calls.append("a:init")

            @on_start
            def start(self) -> None:
                calls.append("a:start")

        @service("b", deps=[A])
        class B:
            @on_init
            def init(self) -> None:
                calls.append("b:init")

            @on_start
            def start(self) -> None:
                calls.append("b:start")

        @module("m", services=[A, B])
        class M:
            pass

        app = Canary(M)
        await app.config()
        await app.init()
        await app.start()

        idx_a_init = calls.index("a:init")
        idx_b_init = calls.index("b:init")
        assert idx_a_init < idx_b_init

    async def test_reverse_shutdown_order(self) -> None:
        calls: list[str] = []

        @service("a")
        class A:
            @on_end
            def stop(self) -> None:
                calls.append("a:stop")

        @service("b", deps=[A])
        class B:
            @on_end
            def stop(self) -> None:
                calls.append("b:stop")

        @module("m", services=[A, B])
        class M:
            pass

        app = Canary(M)
        await app.config()
        await app.init()
        await app.start()
        calls.clear()
        await app.stop()

        # b should stop before a (reverse topological)
        idx_b = calls.index("b:stop")
        idx_a = calls.index("a:stop")
        assert idx_b < idx_a

    async def test_dependency_injection_in_init(self) -> None:
        @service("a")
        class A:
            def do(self) -> str:
                return "a"

        @service("b", deps=[A])
        class B:
            ok: str = ""

            @on_init
            def init(self) -> None:
                self.ok = self.a.do()  # type: ignore[attr-defined]

        @module("m", services=[A, B])
        class M:
            pass

        app = Canary(M)
        await app.config()
        await app.init()
        await app.start()

        assert app.registry.get_by_name("b").instance.ok == "a"  # type: ignore[attr-defined]

    async def test_config_loaded_before_init(self) -> None:
        class MyCfg(BaseModel):
            name: str = "canary"

        class AppConfig(BaseModel):
            configured: MyCfg = MyCfg()

        captured: dict[str, object] = {}

        @service("configured")
        class Configured:
            @on_init
            def init(self) -> None:
                captured["name"] = self.name  # type: ignore[attr-defined]

        app = Canary(Configured)
        await app.config(config=AppConfig())
        await app.init()

        assert captured.get("name") == "canary"

    async def test_config_inheritance(self) -> None:
        class CfgModel(BaseModel):
            env: str = "test"

        class AppConfig(BaseModel):
            child: CfgModel = CfgModel()

        @service("child")
        class Child:
            got: str = ""

            @on_init
            def init(self) -> None:
                self.got = self.env  # type: ignore[attr-defined]

        @module("root", services=[Child])
        class Root:
            pass

        app = Canary(Root)
        await app.config(config=AppConfig())
        await app.init()

        child_inst = app.registry.get_by_name("child").instance
        assert child_inst.got == "test"  # type: ignore[attr-defined]

    async def test_validate_missing_dependency_raises(self) -> None:
        @service("orphan")
        class Orphan:
            pass

        # Manually create a scenario where dep_names references an unregistered service
        app = Canary(Orphan)
        # _collect must run first to register Orphan
        app._collect(Orphan)
        entry = app.registry.get_by_class(Orphan)
        entry.dep_names.append("nonexistent")

        with pytest.raises(ValueError, match="not registered"):
            app._validate()

    async def test_startup_order_property(self) -> None:
        @service("a")
        class A:
            pass

        @service("b", deps=[A])
        class B:
            pass

        @module("m", services=[A, B])
        class M:
            pass

        app = Canary(M)
        await app.config()
        order = app.startup_order
        assert len(order) == 3  # M, A, B (M has no hooks/deps)
        assert order[order.index("a")] == "a"
        assert order[order.index("b")] == "b"

    async def test_registry_property(self) -> None:
        @service("rx")
        class Rx:
            pass

        app = Canary(Rx)
        assert isinstance(app.registry, Registry)


@pytest.mark.integration
class TestCanaryNoHooks:
    """Services without hooks should work without errors."""

    async def test_service_without_hooks(self) -> None:
        @service("silent")
        class Silent:
            pass

        app = Canary(Silent)
        await app.config()
        await app.init()
        await app.start()
        await app.stop()

    async def test_module_without_hooks(self) -> None:
        @service("leaf")
        class Leaf:
            pass

        @module("root", services=[Leaf])
        class Root:
            pass

        app = Canary(Root)
        await app.config()
        await app.init()
        await app.start()
        await app.stop()


@pytest.mark.integration
class TestCanaryCollections:
    """Verify that nested modules collect all services."""

    async def test_nested_modules_collect_all(self) -> None:
        @service("leaf-a")
        class LeafA:
            pass

        @service("leaf-b")
        class LeafB:
            pass

        @module("inner", services=[LeafB])
        class Inner:
            pass

        @module("root", services=[LeafA, Inner])
        class Root:
            pass

        app = Canary(Root)
        await app.config()

        names = app.registry.names()
        assert "root" in names
        assert "inner" in names
        assert "leaf-a" in names
        assert "leaf-b" in names


@pytest.mark.integration
class TestCanaryAsyncHooks:
    """Verify that async lifecycle hooks are properly awaited."""

    async def test_async_on_init(self) -> None:
        called = False

        @service("async-init")
        class AsyncInit:
            @on_init
            async def init(self) -> None:
                nonlocal called
                called = True

        app = Canary(AsyncInit)
        await app.config()
        await app.init()
        assert called is True

    async def test_async_on_start(self) -> None:
        called = False

        @service("async-start")
        class AsyncStart:
            @on_start
            async def start(self) -> None:
                nonlocal called
                called = True

        app = Canary(AsyncStart)
        await app.config()
        await app.init()
        await app.start()
        assert called is True

    async def test_async_on_end(self) -> None:
        called = False

        @service("async-end")
        class AsyncEnd:
            @on_end
            async def stop(self) -> None:
                nonlocal called
                called = True

        app = Canary(AsyncEnd)
        await app.config()
        await app.init()
        await app.start()
        await app.stop()
        assert called is True

    async def test_mixed_sync_async_hooks(self) -> None:
        log: list[str] = []

        @service("mixed")
        class Mixed:
            @on_init
            async def init(self) -> None:
                log.append("init:async")

            @on_start
            def start(self) -> None:
                log.append("start:sync")

            @on_end
            async def end(self) -> None:
                log.append("end:async")

        app = Canary(Mixed)
        await app.config()
        await app.init()
        await app.start()
        await app.stop()
        assert log == ["init:async", "start:sync", "end:async"]


@pytest.mark.integration
class TestCanaryEdgeCases:
    """Edge cases to achieve full branch coverage."""

    async def test_hook_raises_produces_lifecycle_error(self) -> None:
        @service("broken")
        class Broken:
            @on_init
            def init(self) -> None:
                raise RuntimeError("crash")

        app = Canary(Broken)
        await app.config()
        with pytest.raises(LifecycleHookError, match="crash"):
            await app.init()

    def test_collect_non_decorated_class_raises(self) -> None:
        class NotDecorated:
            pass

        @service("dummy")
        class Dummy:
            pass

        app = Canary(Dummy)
        with pytest.raises(TypeError, match="not decorated"):
            app._collect(NotDecorated)

    async def test_collect_duplicate_entry_is_idempotent(self) -> None:
        """Collecting the same class twice skips registration (line 273)."""

        @service("dup")
        class Duplicate:
            pass

        @module("dup-mod", services=[Duplicate, Duplicate])
        class DupMod:
            pass

        app = Canary(DupMod)
        await app.config()
        assert len(app.registry) == 2  # DupMod + Duplicate (only one Duplicate)

    def test_lifecycle_error_is_framework_error(self) -> None:
        assert issubclass(LifecycleHookError, CanaryFrameworkError)
