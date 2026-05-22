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

def test_startup_order():
    Canary(M).start()
    assert _log.index("a:init") < _log.index("b:init")

def test_dep_injection():
    c = Canary(M); c.start()
    assert c._registry.get_by_name("b").instance._ok == "a"

def test_shutdown():
    c = Canary(M); c.start(); _log.clear(); c.stop(); Canary(M).start()
