"""Unit tests for @module decorator."""

from __future__ import annotations

import pytest

from canary_framework.common import ModuleMeta, get_module_meta, is_cf_module
from canary_framework.decorators import after_init, module, service


class TestModuleDecorator:
    def test_module_injects_module_base(self) -> None:
        @module("test-mod")
        class MyModule:
            pass

        assert is_cf_module(MyModule) is True

    def test_is_cf_module_on_service(self) -> None:
        @service("svc")
        class Svc:
            pass

        assert is_cf_module(Svc) is False

    def test_get_module_meta(self) -> None:
        @service("leaf")
        class Leaf:
            pass

        @module("parent", services=[Leaf])
        class Parent:
            pass

        meta = get_module_meta(Parent)
        assert isinstance(meta, ModuleMeta)
        assert meta.name == "parent"
        assert meta.services == [Leaf]

    def test_module_rejects_non_decorated(self) -> None:
        class Plain:
            pass

        with pytest.raises(TypeError, match="not decorated"):

            @module("bad", services=[Plain])
            class Bad:
                pass


class TestModuleLifecycle:
    async def test_config_and_init(self) -> None:
        calls: list[str] = []

        @service("leaf")
        class Leaf:
            @after_init
            def init(self) -> None:
                calls.append("leaf:init")

        @module("root", services=[Leaf])
        class Root:
            pass

        app = Root()
        await app.configure()  # type: ignore[attr-defined]
        await app.init()  # type: ignore[attr-defined]
        assert "leaf:init" in calls

    async def test_topological_order(self) -> None:
        @service("a")
        class A:
            pass

        @service("b", deps=[A])
        class B:
            pass

        @module("m", services=[A, B])
        class M:
            pass

        app = M()
        await app.configure()  # type: ignore[attr-defined]
        order = app._cf_startup_order  # type: ignore[attr-defined]
        assert order.index("a") < order.index("b")

    async def test_empty_module(self) -> None:
        @module("empty")
        class Empty:
            pass

        app = Empty()
        await app.configure()  # type: ignore[attr-defined]
        await app.init()  # type: ignore[attr-defined]
        await app.startup()  # type: ignore[attr-defined]
        await app.shutdown()  # type: ignore[attr-defined]
