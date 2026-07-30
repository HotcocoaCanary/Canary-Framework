"""Large-scale module and router initialization benchmarks."""

from __future__ import annotations

import time
from typing import Any, Literal

import pytest

from canary_framework import config, get, module, router
from canary_framework.common import RouteContext
from canary_framework.common.config import CanaryConfig
from canary_framework.core import ModuleBase, RouterBase


@config()
class BenchConfig(CanaryConfig):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "WARNING"


def _make_router_cls(name: str) -> type[RouterBase]:
    async def handle(self: RouterBase) -> dict[str, Any]:
        return {"name": name}

    namespace = {"handle": get(f"/{name}")(handle)}
    return router()(type(name, (RouterBase,), namespace))


def _make_module_cls(
    name: str, children: list[type], with_config: bool = False
) -> type[ModuleBase]:
    cls = type(name, (ModuleBase,), {})
    return module(children=children, config=BenchConfig if with_config else None)(cls)


@pytest.mark.slow
@pytest.mark.functional
class TestLargeScaleStartup:
    async def test_flat_500_routers(self) -> None:
        children = [_make_router_cls(f"Router{i:03d}") for i in range(500)]
        root = _make_module_cls("Root", children, with_config=True)

        started = time.perf_counter()
        app = root()
        constructed = time.perf_counter()
        await app.init()
        initialized = time.perf_counter()

        print(
            f"\n  Flat 500: __init__={(constructed - started) * 1000:.1f}ms "
            f"init()={(initialized - constructed) * 1000:.1f}ms"
        )
        assert len(app.direct_children) == 500
        assert len(app._collect_routes(RouteContext())) == 500

    async def test_nested_5x100(self) -> None:
        modules = [
            _make_module_cls(
                f"SubMod{i}",
                [_make_router_cls(f"Mod{i}Router{j:03d}") for j in range(100)],
            )
            for i in range(5)
        ]
        app = _make_module_cls("Root", modules, with_config=True)()
        await app.init()

        assert len(app.direct_children) == 5
        assert all(len(child.direct_children) == 100 for child in app.direct_children)  # type: ignore[attr-defined]

    async def test_deep_100_modules(self) -> None:
        previous = _make_module_cls("Lvl099", [_make_router_cls("Leaf")])
        for index in range(98, -1, -1):
            previous = _make_module_cls(
                f"Lvl{index:03d}",
                [_make_router_cls(f"Lvl{index}Router"), previous],
                with_config=index == 0,
            )

        app = previous()
        await app.init()
        assert len(app.direct_children) == 2
