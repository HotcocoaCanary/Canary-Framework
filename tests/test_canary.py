import asyncio

from cf.core import service, on_init, on_start, on_end, Canary, module

_log: list[str] = []


@service("a")
class A:
    @on_init
    def init(self, ctx): _log.append("a:init")
    @on_start
    def start(self): _log.append("a:start")
    def do(self): return "a"

@service("b", deps=[A])
class B:
    @on_init
    def init(self, ctx): _log.append("b:init"); self._ok = self.a.do()
    @on_start
    def start(self): _log.append("b:start")

@module("m", services=[A, B])
class M:
    @on_init
    def init(self, ctx): _log.append("m:init")

import pytest

@pytest.fixture(autouse=True)
def _r(): _log.clear()


async def test_startup_order():
    app = Canary(M)
    await app.init()
    await app.start()
    assert _log.index("a:init") < _log.index("b:init")


async def test_dep_injection():
    app = Canary(M)
    await app.init()
    await app.start()
    assert app.registry.get_by_name("b").instance._ok == "a"


async def test_shutdown():
    app = Canary(M)
    await app.init()
    await app.start()
    _log.clear()
    await app.stop()
