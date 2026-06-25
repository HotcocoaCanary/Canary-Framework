"""Benchmark: large-scale module/service startup performance.

Tests framework init/startup with 500+ services in various topologies.
"""

from __future__ import annotations

import time
from typing import Any, Literal

import pytest

from canary_framework import config, module, service
from canary_framework.common.config import CanaryConfig
from canary_framework.common.types import CF_NAME_ATTR, CF_SERVICE_META, ModuleMeta, ServiceMeta
from canary_framework.core.module import ModuleBase
from canary_framework.core.router import Router
from canary_framework.core.service import ServiceBase


# ── Config ────────────────────────────────────────────────
@config()
class BenchConfig(CanaryConfig):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "WARNING"


# ── Class factories ───────────────────────────────────────
def _make_service_cls(name: str) -> type[ServiceBase]:
    """Create a minimal service class with one GET route."""

    @service()
    class Svc(ServiceBase):
        router = Router()

        @router.get(f"/{name}")
        async def handle(self) -> dict[str, Any]:
            return {"name": name}

    Svc.__name__ = name
    Svc.__qualname__ = name
    meta: ServiceMeta = getattr(Svc, CF_SERVICE_META)
    meta.name = name
    setattr(Svc, CF_NAME_ATTR, name)
    return Svc


def _make_module_cls(
    name: str, services: list[type], with_config: bool = False
) -> type[ModuleBase]:
    """Create a module class with given sub-services."""
    kw: dict[str, Any] = {"services": services}
    if with_config:
        kw["config"] = BenchConfig

    @module(**kw)
    class Mod(ModuleBase):
        pass

    Mod.__name__ = name
    Mod.__qualname__ = name
    meta: ModuleMeta = getattr(Mod, CF_SERVICE_META)
    meta.name = name
    setattr(Mod, CF_NAME_ATTR, name)
    return Mod


# ── Tests ─────────────────────────────────────────────────
@pytest.mark.slow
@pytest.mark.functional
class TestLargeScaleStartup:
    """Benchmark framework startup with 500 services."""

    def test_flat_500_services(self) -> None:
        """500 services registered flat under one root module."""
        services = [_make_service_cls(f"Svc{i:03d}") for i in range(500)]
        root = _make_module_cls("Root", services, with_config=True)

        t0 = time.perf_counter()
        app = root()
        t1 = time.perf_counter()
        app.init()
        t2 = time.perf_counter()
        print(f"\n  Flat 500: __init__={(t1 - t0) * 1000:.1f}ms  init()={(t2 - t1) * 1000:.1f}ms")

        assert app._cf_registry is not None
        assert len(app._cf_startup_order) == 500

    def test_nested_5x100(self) -> None:
        """5 sub-modules × 100 services each = 500 total."""
        modules: list[type[ModuleBase]] = []
        for i in range(5):
            services = [_make_service_cls(f"Mod{i}Svc{j:03d}") for j in range(100)]
            modules.append(_make_module_cls(f"SubMod{i}", services))
        root = _make_module_cls("Root", modules, with_config=True)

        t0 = time.perf_counter()
        app = root()
        t1 = time.perf_counter()
        app.init()
        t2 = time.perf_counter()
        print(
            f"\n  Nested 5×100: __init__={(t1 - t0) * 1000:.1f}ms  init()={(t2 - t1) * 1000:.1f}ms"
        )

        assert app._cf_registry is not None

    def test_deep_100_modules(self) -> None:
        """100 levels deep, 5 services per level = 500 services."""
        # Bottom level: 5 leaf services
        leaf_svcs = [_make_service_cls(f"Leaf{j:03d}") for j in range(5)]
        prev_module = _make_module_cls("Lvl099", leaf_svcs)

        # Build chain upwards: each level wraps previous + 5 services
        for i in range(98, -1, -1):
            services = [_make_service_cls(f"Lvl{i}Svc{j:03d}") for j in range(5)]
            services.append(prev_module)
            prev_module = _make_module_cls(f"Lvl{i:03d}", services, with_config=(i == 0))

        t0 = time.perf_counter()
        app = prev_module()
        t1 = time.perf_counter()
        app.init()
        t2 = time.perf_counter()
        print(f"\n  Deep 100: __init__={(t1 - t0) * 1000:.1f}ms  init()={(t2 - t1) * 1000:.1f}ms")

        assert app._cf_registry is not None
