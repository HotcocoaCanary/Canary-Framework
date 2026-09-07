"""Integration — units are constructed with no arguments, and that rule says so.

单元由框架无参构造。这条约束一直存在，此前失败时只抛构造器自己的 TypeError。
"""

from __future__ import annotations

import pytest

from canary_framework import Canary, CanaryError, ConstructionError, cocoa

pytestmark = pytest.mark.integration


@cocoa
class NeedsArguments:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn


@cocoa(deps=[NeedsArguments])
class Consumer:
    pass


async def test_a_unit_that_needs_arguments_says_what_to_do() -> None:
    canary = Canary(Consumer)
    with pytest.raises(ConstructionError, match="constructed with no arguments") as caught:
        await canary.init()

    message = str(caught.value)
    assert "provide=" in message  # 报错要指出出路
    assert isinstance(caught.value, CanaryError)  # 兜得进框架的错误体系


async def test_providing_the_instance_is_the_way_out() -> None:
    async with Canary(Consumer, provide={NeedsArguments: NeedsArguments("postgres://x")}) as app:
        assert app[Consumer].needs_arguments.dsn == "postgres://x"


async def test_default_arguments_are_fine() -> None:
    @cocoa
    class HasDefaults:
        def __init__(self, dsn: str = "sqlite://") -> None:
            self.dsn = dsn

    async with Canary(HasDefaults) as app:
        assert app[HasDefaults].dsn == "sqlite://"


async def test_an_error_inside_a_constructor_is_not_disguised() -> None:
    """签名对得上就照常调用——构造器自己抛的异常是使用者的代码出错，不该被盖住。"""

    @cocoa
    class Explodes:
        def __init__(self) -> None:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await Canary(Explodes).init()
