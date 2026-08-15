"""Integration — mixin hooks compose with (rather than clobber) a class's own hooks."""

import pytest

from canary_framework import Canary, cocoa, on_start

pytestmark = pytest.mark.integration


def test_mixin_hooks_run_before_the_class_hooks() -> None:
    calls: list[str] = []

    class AuditMixin:
        @on_start
        def audit(self) -> None:
            calls.append(f"{type(self).__name__}.audit")

    @cocoa
    class UserService(AuditMixin):
        @on_start
        def start(self) -> None:
            calls.append(f"{type(self).__name__}.start")

    with Canary(UserService):
        pass

    # 混入的钩子先于本类的钩子执行，二者都保留（未被覆盖）。
    assert calls == ["UserService.audit", "UserService.start"]


def test_one_mixin_composes_across_many_services() -> None:
    calls: list[str] = []

    class AuditMixin:
        @on_start
        def audit(self) -> None:
            calls.append(f"{type(self).__name__}.audit")

    @cocoa
    class UserService(AuditMixin):
        @on_start
        def start(self) -> None:
            calls.append(f"{type(self).__name__}.start")

    @cocoa
    class OrderService(AuditMixin):
        @on_start
        def start(self) -> None:
            calls.append(f"{type(self).__name__}.start")

    with Canary(UserService, OrderService):
        pass

    # 每个服务各自得到「混入钩子 + 本类钩子」，按拓扑序交错执行。
    assert calls == [
        "UserService.audit",
        "UserService.start",
        "OrderService.audit",
        "OrderService.start",
    ]
