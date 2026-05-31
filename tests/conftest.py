"""Shared test fixtures."""

from __future__ import annotations

import pytest

from canary_framework.decorators import (
    after_init,
    before_shutdown,
    before_startup,
    module,
    service,
)


@service("a")
class ServiceA:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    @after_init
    def hook_init(self) -> None:
        self.calls.append("a:init")

    @before_startup
    def hook_start(self) -> None:
        self.calls.append("a:start")

    @before_shutdown
    def hook_end(self) -> None:
        self.calls.append("a:end")

    def do(self) -> str:
        return "a"


@service("b", deps=[ServiceA])
class ServiceB:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    @after_init
    def hook_init(self) -> None:
        self.calls.append("b:init")

    @before_startup
    def hook_start(self) -> None:
        self.calls.append("b:start")

    @before_shutdown
    def hook_end(self) -> None:
        self.calls.append("b:end")


@service("c", deps=[ServiceB])
class ServiceC:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    @after_init
    def hook_init(self) -> None:
        self.calls.append("c:init")

    @before_startup
    def hook_start(self) -> None:
        self.calls.append("c:start")


@module("m", services=[ServiceA, ServiceB])
class ModuleM:
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    @after_init
    def hook_init(self) -> None:
        self.calls.append("m:init")


@pytest.fixture
def module_instance() -> ModuleM:
    return ModuleM()


@pytest.fixture
async def init_module() -> ModuleM:
    inst = ModuleM()
    await inst.configure()  # type: ignore[attr-defined]
    await inst.init()  # type: ignore[attr-defined]
    return inst
