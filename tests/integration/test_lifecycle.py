"""Integration tests for framework lifecycle."""

from __future__ import annotations

import pytest

from canary_framework.common import CircularDependencyError, LifecycleHookError
from canary_framework.decorators import (
    after_init,
    before_shutdown,
    before_startup,
    module,
    service,
)
from canary_framework.engine import Registry


class TestLifecycle:
    async def test_init_startup_shutdown_flow(self) -> None:
        calls: list[str] = []

        @service("hello")
        class Hello:
            @after_init
            def hook_init(self) -> None:
                calls.append("init")

            @before_startup
            def hook_start(self) -> None:
                calls.append("startup")

            @before_shutdown
            def hook_shutdown(self) -> None:
                calls.append("shutdown")

        app = Hello()
        await app.configure()  # type: ignore[attr-defined]
        await app.init()  # type: ignore[attr-defined]
        await app.startup()  # type: ignore[attr-defined]
        await app.shutdown()  # type: ignore[attr-defined]
        assert calls == ["init", "startup", "shutdown"]

    async def test_topological_order(self) -> None:
        calls: list[str] = []

        @service("a")
        class A:
            @after_init
            def hook_init(self) -> None:
                calls.append("a:init")

        @service("b", deps=[A])
        class B:
            @after_init
            def hook_init(self) -> None:
                calls.append("b:init")

        @module("m", services=[A, B])
        class M:
            pass

        app = M()
        await app.configure()  # type: ignore[attr-defined]
        await app.init()  # type: ignore[attr-defined]
        assert calls.index("a:init") < calls.index("b:init")

    async def test_reverse_shutdown_order(self) -> None:
        calls: list[str] = []

        @service("a")
        class A:
            @before_shutdown
            def hook_shutdown(self) -> None:
                calls.append("a:stop")

        @service("b", deps=[A])
        class B:
            @before_shutdown
            def hook_shutdown(self) -> None:
                calls.append("b:stop")

        @module("m", services=[A, B])
        class M:
            pass

        app = M()
        await app.configure()  # type: ignore[attr-defined]
        await app.init()  # type: ignore[attr-defined]
        await app.startup()  # type: ignore[attr-defined]
        await app.shutdown()  # type: ignore[attr-defined]
        assert calls.index("b:stop") < calls.index("a:stop")

    async def test_config_loaded_before_init(self) -> None:
        class AppConfig:
            name: str = "canary"

        captured: dict[str, str] = {}

        @service("configured")
        class Configured:
            @after_init
            def hook_init(self) -> None:
                captured["name"] = self.config.name  # type: ignore[attr-defined]

        app = Configured()
        await app.configure(AppConfig())  # type: ignore[attr-defined]
        await app.init()  # type: ignore[attr-defined]
        assert captured.get("name") == "canary"

    async def test_hook_error_wraps_in_lifecycle_error(self) -> None:
        @service("broken")
        class Broken:
            @after_init
            def hook_init(self) -> None:
                raise RuntimeError("crash")

        app = Broken()
        await app.configure()  # type: ignore[attr-defined]
        with pytest.raises(LifecycleHookError, match="crash"):
            await app.init()  # type: ignore[attr-defined]


class TestCircularDependency:
    async def test_circular_detected(self) -> None:
        from canary_framework.engine import topological_sort

        @service("a")
        class A:
            pass

        @service("b")
        class B:
            pass

        reg = Registry()
        reg.register(A)
        reg.register(B)
        a_entry = reg.get_by_class(A)
        a_entry.dep_names = ["b"]
        b_entry = reg.get_by_class(B)
        b_entry.dep_names = ["a"]

        with pytest.raises(CircularDependencyError):
            topological_sort(reg)
