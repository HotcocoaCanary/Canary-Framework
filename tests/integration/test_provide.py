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
