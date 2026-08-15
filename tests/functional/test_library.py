"""End-to-end functional test: a small library-management scenario."""

import pytest

from canary_framework import Canary, cocoa, on_init

pytestmark = pytest.mark.functional


def _build_library() -> type:
    @cocoa
    class Config:
        @on_init
        def load(self) -> None:
            self.settings = {"db_name": "test.db"}

    @cocoa(deps=[Config])
    class Database:
        @on_init
        def seed(self) -> None:
            self.tables = {
                "books": [
                    {"id": 1, "title": "三体", "stock": 1},
                    {"id": 2, "title": "活着", "stock": 0},
                ],
                "members": [{"id": 1, "name": "张三"}],
                "loans": [],
            }

    @cocoa(deps=[Database])
    class BookRepository:
        def get(self, book_id: int) -> dict | None:
            return next((b for b in self.database.tables["books"] if b["id"] == book_id), None)

    @cocoa(deps=[Database])
    class MemberRepository:
        def get(self, member_id: int) -> dict | None:
            return next((m for m in self.database.tables["members"] if m["id"] == member_id), None)

    @cocoa(deps=[Database, BookRepository])
    class LoanRepository:
        def borrow(self, member_id: int, book_id: int) -> str:
            book = self.book_repository.get(book_id)
            if book is None or book["stock"] <= 0:
                return "借阅失败：无库存"
            book["stock"] -= 1
            self.database.tables["loans"].append({"member_id": member_id, "book_id": book_id})
            return f"借出《{book['title']}》"

    @cocoa(deps=[BookRepository, MemberRepository, LoanRepository])
    class LibraryService:
        def borrow(self, member_id: int, book_id: int) -> str:
            member = self.member_repository.get(member_id)
            assert member is not None
            return f"{member['name']}：{self.loan_repository.borrow(member_id, book_id)}"

    @cocoa(deps=[LibraryService])
    class LibraryApp:
        pass

    return LibraryApp


def test_full_library_lifecycle() -> None:
    app_type = _build_library()

    with Canary(app_type) as canary:
        svc = canary[app_type].library_service

        assert svc.borrow(1, 1) == "张三：借出《三体》"
        assert svc.borrow(1, 2) == "张三：借阅失败：无库存"  # 无库存

    # 依赖图按拓扑序：Config → Database → Repos → LibraryService → LibraryApp
    assert canary.order[0].__name__ == "Config"
    assert canary.order[-1] is app_type
    assert canary.state.name == "STOPPED"


def test_repository_can_run_standalone() -> None:
    app_type = _build_library()
    with Canary(app_type) as canary:
        book_repo = canary[app_type].library_service.book_repository

    # 单独启动一个仓库，只拉起它自己的子树
    repo_type = type(book_repo)
    with Canary(repo_type) as solo:
        assert [t.__name__ for t in solo.order] == ["Config", "Database", "BookRepository"]
