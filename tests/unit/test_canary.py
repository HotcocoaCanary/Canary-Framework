"""Unit tests for the Canary runtime."""

import subprocess
import sys

import pytest

from canary_framework import Canary, LifecycleState, cocoa, on_init, on_start, on_stop
from canary_framework.common.error import CircularDependencyError, LifecycleError

pytestmark = pytest.mark.unit


async def test_lifecycle_state_transitions() -> None:
    @cocoa
    class Service:
        pass

    canary = Canary(Service)
    assert canary.state is LifecycleState.NEW
    await canary.init()
    assert canary.state is LifecycleState.INITIALIZED
    await canary.start()
    assert canary.state is LifecycleState.STARTED
    await canary.stop()
    assert canary.state is LifecycleState.STOPPED


async def test_hooks_run_in_topological_order() -> None:
    calls: list[str] = []

    @cocoa
    class A:
        @on_init
        def init(self) -> None:
            calls.append("A.init")

        @on_start
        def start(self) -> None:
            calls.append("A.start")

        @on_stop
        def stop(self) -> None:
            calls.append("A.stop")

    @cocoa(deps=[A])
    class B:
        @on_start
        def start(self) -> None:
            calls.append("B.start")

    canary = Canary(B)
    await canary.init()
    assert calls == ["A.init"]

    await canary.start()
    assert calls == ["A.init", "A.start", "B.start"]

    await canary.stop()
    assert calls == ["A.init", "A.start", "B.start", "A.stop"]


async def test_dependencies_are_injected_during_init() -> None:
    """注入属于装配：``init()`` 结束时单元已接好线，``@on_init`` 因此能用依赖。"""
    seen: list[object] = []

    @cocoa
    class Dep:
        pass

    @cocoa(deps=[Dep])
    class Service:
        @on_init
        def check(self) -> None:
            seen.append(self.dep)

    canary = Canary(Service)
    await canary.init()

    assert isinstance(canary[Service].dep, Dep)
    assert seen == [canary[Dep]]  # @on_init 看得到依赖，且拿到的是图上的那个实例


async def test_singleton_is_shared_across_the_graph() -> None:
    @cocoa
    class Dep:
        pass

    @cocoa(deps=[Dep])
    class A:
        pass

    @cocoa(deps=[Dep])
    class B:
        pass

    @cocoa(deps=[A, B])
    class Root:
        pass

    canary = Canary(Root)
    await canary.init()
    await canary.start()
    assert canary[Root].a.dep is canary[Root].b.dep is canary[Dep]


async def test_nesting_standalone_and_composition() -> None:
    @cocoa
    class Config:
        pass

    @cocoa(deps=[Config])
    class Database:
        pass

    @cocoa(deps=[Database])
    class Repo:
        pass

    @cocoa(deps=[Repo])
    class App:
        pass

    nested = Canary(App)
    await nested.init()
    await nested.start()
    assert nested.order == (Config, Database, Repo, App)

    standalone = Canary(Database)
    await standalone.init()
    await standalone.start()
    assert standalone.order == (Config, Database)

    composed = Canary(Config, Repo)
    await composed.init()
    await composed.start()
    assert set(composed.order) == {Config, Database, Repo}


async def test_start_stop_drives_full_lifecycle() -> None:
    @cocoa
    class Service:
        @on_start
        def start(self) -> None:
            self.running = True

        @on_stop
        def stop(self) -> None:
            self.running = False

    canary = Canary(Service)
    await canary.init()
    await canary.start()
    assert canary.state is LifecycleState.STARTED
    assert canary[Service].running is True

    await canary.stop()
    assert canary.state is LifecycleState.STOPPED
    assert canary[Service].running is False


async def test_start_requires_init() -> None:
    @cocoa
    class Service:
        pass

    canary = Canary(Service)
    with pytest.raises(LifecycleError):
        await canary.start()  # 未 init 直接 start → 非法跳转


def test_non_cocoa_root_raises_type_error() -> None:
    class Plain:
        pass

    with pytest.raises(TypeError, match="not decorated with @cocoa"):
        Canary(Plain)


async def test_cycle_fails_the_canary() -> None:
    @cocoa
    class A:
        pass

    @cocoa(deps=[A])
    class B:
        pass

    A.__cocoa_deps__ = [B]  # close the loop A <-> B

    canary = Canary(A)
    with pytest.raises(CircularDependencyError):
        await canary.init()
    assert canary.state is LifecycleState.FAILED


async def test_illegal_transition_raises() -> None:
    @cocoa
    class Service:
        pass

    canary = Canary(Service)
    with pytest.raises(LifecycleError):
        await canary.start()  # 不能跳过 init 直接启动

    await canary.init()
    with pytest.raises(LifecycleError):
        await canary.init()  # 不能重复初始化


def test_plain_cocoa_composition_does_not_import_the_web_extension() -> None:
    """web 是可选额外依赖：不带路由的编排不该把 web 扩展（及 starlette）拉进来。"""
    code = (
        "import asyncio, sys\n"
        "from canary_framework import Canary, cocoa\n"
        "@cocoa\n"
        "class Unit: ...\n"
        "async def main():\n"
        "    async with Canary(Unit):\n"
        "        pass\n"
        "asyncio.run(main())\n"
        "assert 'canary_framework.web' not in sys.modules, 'web extension imported'\n"
        "assert 'starlette' not in sys.modules, 'starlette imported'\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
