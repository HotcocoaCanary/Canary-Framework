"""Integration — units are constructed with no arguments, and that rule says so.

单元由框架无参构造。这条约束一直存在，此前失败时只抛构造器自己的 TypeError。
"""

from __future__ import annotations

import pytest

from canary_framework import Canary, CanaryError, ConstructionError, cocoa, on_init

pytestmark = pytest.mark.integration


@cocoa
class NeedsArguments:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn


@cocoa(deps=[NeedsArguments])
class Consumer:
    pass


async def test_a_unit_that_needs_arguments_says_what_to_do() -> None:
    with pytest.raises(ConstructionError, match="constructed with no arguments") as caught:
        Canary(Consumer)  # 装配期错误，在构造这一行就抛

    message = str(caught.value)
    assert "@cocoa(deps=" in message  # 报错要指出唯一的出路
    assert "@on_init" in message
    assert isinstance(caught.value, CanaryError)  # 兜得进框架的错误体系


async def test_taking_the_value_from_a_dependency_is_the_way_out() -> None:
    """唯一的出路：把构造参数变成依赖，值在生命周期里读。"""

    @cocoa
    class Settings:
        def __init__(self) -> None:
            self.dsn = "postgres://x"

    @cocoa(deps=[Settings])
    class Database:
        @on_init
        def take_the_dsn(self) -> None:
            self.dsn = self.settings.dsn

    async with Canary(Database) as app:
        assert app[Database].dsn == "postgres://x"


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
        Canary(Explodes)


async def test_a_type_error_from_inside_the_constructor_is_not_relabelled() -> None:
    """签名对得上时构造器自己抛的 TypeError 必须原样传播。

    这条是 _construct 的顺序（先构造、出错再回头看签名）的保险：两种 TypeError 长得一样，
    只能靠签名分辨——签名压根对不上才是框架的约束，其余都是使用者的代码。
    """

    @cocoa
    class Explodes:
        def __init__(self) -> None:
            raise TypeError("raised by my own body")

    with pytest.raises(TypeError, match="raised by my own body") as caught:
        Canary(Explodes)
    assert not isinstance(caught.value, ConstructionError)


async def test_default_and_variadic_arguments_construct_fine() -> None:
    @cocoa
    class Flexible:
        def __init__(self, *args: object, dsn: str = "sqlite://", **kwargs: object) -> None:
            self.dsn = dsn

    async with Canary(Flexible) as app:
        assert app[Flexible].dsn == "sqlite://"
