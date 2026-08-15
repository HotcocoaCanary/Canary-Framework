"""Unit tests for the Canary runtime."""

import pytest

from canary_framework import Canary, LifecycleState, cocoa, on_init, on_start, on_stop
from canary_framework.common.error import CircularDependencyError, LifecycleError

pytestmark = pytest.mark.unit


def test_lifecycle_state_transitions() -> None:
    @cocoa
    class Service:
        pass

    canary = Canary(Service)
    assert canary.state is LifecycleState.NEW
    canary.init()
    assert canary.state is LifecycleState.INITIALIZED
    canary.start()
    assert canary.state is LifecycleState.STARTED
    canary.stop()
    assert canary.state is LifecycleState.STOPPED


def test_hooks_run_in_topological_order() -> None:
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
    canary.init()
    assert calls == ["A.init"]

    canary.start()
    assert calls == ["A.init", "A.start", "B.start"]

    canary.stop()
    assert calls == ["A.init", "A.start", "B.start", "A.stop"]


def test_dependency_injection_is_lazy() -> None:
    @cocoa
    class Dep:
        pass

    @cocoa(deps=[Dep])
    class Service:
        pass

    canary = Canary(Service)
    canary.init()
    assert not hasattr(canary[Service], "dep")  # 未注入

    canary.start()
    assert isinstance(canary[Service].dep, Dep)  # start 阶段注入


def test_singleton_is_shared_across_the_graph() -> None:
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
    canary.init()
    canary.start()
    assert canary[Root].a.dep is canary[Root].b.dep is canary[Dep]


def test_nesting_standalone_and_composition() -> None:
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
    nested.init()
    nested.start()
    assert nested.order == (Config, Database, Repo, App)

    standalone = Canary(Database)
    standalone.init()
    standalone.start()
    assert standalone.order == (Config, Database)

    composed = Canary(Config, Repo)
    composed.init()
    composed.start()
    assert set(composed.order) == {Config, Database, Repo}


def test_context_manager_drives_full_lifecycle() -> None:
    @cocoa
    class Service:
        @on_start
        def start(self) -> None:
            self.running = True

        @on_stop
        def stop(self) -> None:
            self.running = False

    with Canary(Service) as canary:
        assert canary.state is LifecycleState.STARTED
        assert canary[Service].running is True

    assert canary.state is LifecycleState.STOPPED
    assert canary[Service].running is False


def test_non_cocoa_root_raises_type_error() -> None:
    class Plain:
        pass

    with pytest.raises(TypeError, match="not decorated with @cocoa"):
        Canary(Plain)


def test_cycle_fails_the_canary() -> None:
    @cocoa
    class A:
        pass

    @cocoa(deps=[A])
    class B:
        pass

    A.__cocoa_deps__ = [B]  # close the loop A <-> B

    canary = Canary(A)
    with pytest.raises(CircularDependencyError):
        canary.init()
    assert canary.state is LifecycleState.FAILED


def test_illegal_transition_raises() -> None:
    @cocoa
    class Service:
        pass

    canary = Canary(Service)
    with pytest.raises(LifecycleError):
        canary.stop()  # 不能从未启动直接停止

    canary.init()
    with pytest.raises(LifecycleError):
        canary.init()  # 不能重复初始化
