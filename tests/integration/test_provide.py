"""Integration — handing the runtime a ready-made instance for a node.

``provide`` 的两种用途共用同一个入口：生产接线（这个节点需要构造参数，我造好了）
与测试替换（用假的顶掉真的）。
"""

from __future__ import annotations

import pytest

from canary_framework import Canary, ProvisionError, cocoa, on_start

pytestmark = pytest.mark.integration


@cocoa
class Database:
    """真实依赖：一旦被构造就会去连库。"""

    def __init__(self) -> None:
        raise AssertionError("the real Database must not be constructed")


@cocoa(deps=[Database])
class Repository:
    async def find(self, book_id: int) -> str:
        return self.database.query(book_id)


@cocoa(deps=[Repository])
class Service:
    async def title_of(self, book_id: int) -> str:
        return await self.repository.find(book_id)


async def test_a_provided_instance_replaces_a_unit_and_skips_its_dependencies() -> None:
    class FakeRepository:
        async def find(self, book_id: int) -> str:
            return f"fake-{book_id}"

    canary = Canary(Service, provide={Repository: FakeRepository()})
    async with canary:
        assert await canary[Service].title_of(7) == "fake-7"

    # 替身自带协作者，所以 Database 根本没被展开——真实构造器会 assert 失败。
    assert Database not in canary.order


async def test_substitute_lifecycle_hooks_still_run() -> None:
    log: list[str] = []

    class FakeRepository:
        @on_start
        async def warm(self) -> None:
            log.append("fake.start")

        async def find(self, book_id: int) -> str:
            return "fake"

    async with Canary(Service, provide={Repository: FakeRepository()}):
        pass

    assert log == ["fake.start"]


async def test_a_provided_type_that_never_applies_is_an_error() -> None:
    """写错类型时静默忽略，会让测试「通过」却根本没替换成功。"""

    @cocoa
    class Lonely:
        pass

    canary = Canary(Lonely, provide={Repository: object()})
    with pytest.raises(ProvisionError, match="Repository"):
        await canary.init()  # 装配类的检查落在装配阶段


async def test_a_substitute_may_not_declare_dependencies() -> None:
    """继承被替换的类（为了让 mypy 认）会把 ``deps`` 标记一起继承。

    从前这里漏出一个裸 ``KeyError``——它不继承 ``CanaryError``，``except CanaryError``
    兜不住，也没说清哪条规则被违背了。
    """

    class StubRepository(Repository):  # 继承只是为了类型检查
        async def find(self, book_id: int) -> str:
            return "stub"

    canary = Canary(Service, provide={Repository: StubRepository()})
    with pytest.raises(ProvisionError, match=r"StubRepository.*Database"):
        await canary.init()


async def test_the_rule_does_not_depend_on_what_else_is_on_the_graph() -> None:
    """同一份写法，从前的行为取决于别的单元有没有恰好依赖同一个类型。

    没人依赖 ``Database`` 时崩 ``KeyError``，有人依赖时静默注入成功——两种行为。
    现在两种图形状给出同一个错误。
    """

    @cocoa(deps=[Database])
    class Neighbour:
        """让 Database 也从另一条路径可达。"""

    @cocoa(deps=[Repository, Neighbour])
    class Root:
        pass

    class StubRepository(Repository):
        pass

    canary = Canary(Root, provide={Repository: StubRepository(), Database: object()})
    with pytest.raises(ProvisionError, match="StubRepository"):
        await canary.init()


async def test_provided_instances_do_not_constrain_the_start_order() -> None:
    """被 provide 的节点不接受注入，就不该因为声明类型上的依赖被排到别人后面。"""
    order: list[str] = []

    @cocoa
    class Leaf:
        @on_start
        async def go(self) -> None:
            order.append("leaf")

    @cocoa(deps=[Leaf])
    class Middle:
        pass

    @cocoa(deps=[Middle, Leaf])
    class Root:
        pass

    class StubMiddle:
        @on_start
        async def go(self) -> None:
            order.append("stub")

    async with Canary(Root, provide={Middle: StubMiddle()}):
        pass

    # 替身不依赖 Leaf，所以它不必等 Leaf——按声明类型排序时它会被排在 Leaf 之后。
    assert order == ["stub", "leaf"]
