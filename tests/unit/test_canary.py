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
    assert canary.state is LifecycleState.READY  # 构造即装配，一出生就可用
    await canary.init()
    assert canary.state is LifecycleState.INITIALIZED  # 各就各位，还没开工
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
    assert calls == []  # 装配不跑任何钩子

    await canary.init()
    await canary.start()  # 先全部 @on_init，再全部 @on_start
    assert calls == ["A.init", "A.start", "B.start"]

    await canary.stop()
    assert calls == ["A.init", "A.start", "B.start", "A.stop"]


async def test_dependencies_are_injected_at_construction() -> None:
    """注入属于装配，而装配在构造函数里：``Canary(...)`` 一返回，线就接好了。"""
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
    assert isinstance(canary[Service].dep, Dep)  # 构造一返回，线就接好了
    assert seen == []  # 但钩子还没跑——装配不是运行

    await canary.init()
    await canary.start()
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


async def test_the_runtime_is_usable_the_moment_it_is_constructed() -> None:
    """这个框架要求每个单元"构造完就必须可用"，运行时自己没有理由例外。"""

    @cocoa
    class Dep:
        pass

    @cocoa(deps=[Dep])
    class Service:
        pass

    canary = Canary(Service)  # 没有 await
    assert canary.state is LifecycleState.READY
    assert canary.order == (Dep, Service)  # 已排好序
    assert canary[Service].dep is canary[Dep]  # 已注入


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

    with pytest.raises(CircularDependencyError):
        Canary(A)  # 装配期错误，在这一行就抛


async def test_illegal_transition_raises() -> None:
    @cocoa
    class Service:
        pass

    canary = Canary(Service)
    await canary.init()
    await canary.start()
    with pytest.raises(LifecycleError):
        await canary.init()
        await canary.start()  # 不能重复启动


def test_a_full_lifecycle_pulls_in_no_third_party_package() -> None:
    """核心零依赖不是 pyproject 里的一句声明，是一条可验证的事实。

    跑完一整轮 init / start / stop 之后，sys.modules 里不该出现任何来自 site-packages
    的东西——框架只用标准库。
    """
    code = (
        "import sys, sysconfig\n"
        "before = set(sys.modules)\n"  # 解释器自带的（含 virtualenv 引导）不算
        "import asyncio\n"
        "from canary_framework import Canary, cocoa, on_init, on_start, on_stop\n"
        "@cocoa\n"
        "class Leaf:\n"
        "    @on_init\n"
        "    def a(self): ...\n"
        "    @on_start\n"
        "    async def b(self): ...\n"
        "    @on_stop\n"
        "    async def c(self): ...\n"
        "@cocoa(deps=[Leaf])\n"
        "class Root: ...\n"
        "async def main():\n"
        "    async with Canary(Root):\n"
        "        pass\n"
        "asyncio.run(main())\n"
        "site = sysconfig.get_paths()['purelib']\n"
        "third = sorted(\n"
        "    name\n"
        "    for name, mod in sys.modules.items()\n"
        "    if name not in before\n"
        "    and getattr(mod, '__file__', None)\n"
        "    and str(mod.__file__).startswith(site)\n"
        "    and not name.startswith('canary_framework')\n"
        ")\n"
        "assert not third, f'third-party imports: {third}'\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


async def test_each_action_runs_exactly_one_hook_phase() -> None:
    """一一对应：init() 只跑 @on_init，start() 只跑 @on_start。栅栏就是两个方法的边界。"""
    calls: list[str] = []

    @cocoa
    class Unit:
        @on_init
        def prepare(self) -> None:
            calls.append("init")

        @on_start
        def go(self) -> None:
            calls.append("start")

    canary = Canary(Unit)
    assert calls == []  # 装配不跑钩子
    await canary.init()
    assert calls == ["init"]  # 各就各位，没有任何单元开工
    await canary.start()
    assert calls == ["init", "start"]


async def test_start_before_init_is_refused_loudly() -> None:
    """忘了 init() 是响的，不是静默失效。"""

    @cocoa
    class Unit:
        pass

    with pytest.raises(LifecycleError, match=r"call init\(\) before start\(\)"):
        await Canary(Unit).start()
