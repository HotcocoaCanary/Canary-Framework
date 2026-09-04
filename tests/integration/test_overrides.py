"""Integration — substituting units at assembly time.

依赖替换：测试里把仓储 / 模型换成替身，业务代码里不留配置开关。
"""

from __future__ import annotations

import pytest

from canary_framework import Canary, OverrideError, cocoa, on_start

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


async def test_override_replaces_a_unit_and_skips_its_dependencies() -> None:
    class FakeRepository:
        async def find(self, book_id: int) -> str:
            return f"fake-{book_id}"

    canary = Canary(Service, overrides={Repository: FakeRepository()})
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

    async with Canary(Service, overrides={Repository: FakeRepository()}):
        pass

    assert log == ["fake.start"]


async def test_an_override_that_never_applies_is_an_error() -> None:
    """写错类型时静默忽略，会让测试「通过」却根本没替换成功。"""

    @cocoa
    class Lonely:
        pass

    canary = Canary(Lonely, overrides={Repository: object()})
    await canary.init()
    with pytest.raises(OverrideError, match="Repository"):
        await canary.start()
