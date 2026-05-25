"""Shared test fixtures and helpers for Canary Framework tests."""

from __future__ import annotations

import pytest

from canary_framework.core import config as _config_decorator
from canary_framework.core import module as _module_decorator
from canary_framework.core import service as _service_decorator
from canary_framework.core.decorators.lifecycle import on_end, on_init, on_start
from canary_framework.core.engine.canary import Canary
from canary_framework.core.engine.context import Context

# ---------------------------------------------------------------------------
# Minimal fixture classes
# ---------------------------------------------------------------------------


@_service_decorator("a")
class ServiceA:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    @on_init
    def init(self, ctx: Context) -> None:
        self.calls.append("a:init")

    @on_start
    def start(self) -> None:
        self.calls.append("a:start")

    @on_end
    def end(self) -> None:
        self.calls.append("a:end")

    def do(self) -> str:
        return "a"


@_service_decorator("b", deps=[ServiceA])
class ServiceB:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    @on_init
    def init(self, ctx: Context) -> None:
        self.calls.append("b:init")

    @on_start
    def start(self) -> None:
        self.calls.append("b:start")

    @on_end
    def end(self) -> None:
        self.calls.append("b:end")


@_service_decorator("c", deps=[ServiceB])
class ServiceC:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    @on_init
    def init(self, ctx: Context) -> None:
        self.calls.append("c:init")

    @on_start
    def start(self) -> None:
        self.calls.append("c:start")


@_module_decorator("m", services=[ServiceA, ServiceB])
class ModuleM:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    @on_init
    def init(self, ctx: Context) -> None:
        self.calls.append("m:init")


@_config_decorator
class TestConfig:
    host: str = "localhost"
    port: int = 9999


@_service_decorator("with-config", config=TestConfig)
class ServiceWithConfig:
    @on_init
    def init(self, ctx: Context) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_canary() -> Canary:
    """Return a fresh Canary instance with ModuleM as root."""
    return Canary(ModuleM)


@pytest.fixture
async def init_canary() -> Canary:
    """Return a Canary instance that has already been initialised."""
    app = Canary(ModuleM)
    await app.init()
    return app
