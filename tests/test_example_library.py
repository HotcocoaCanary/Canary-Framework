"""端到端：examples/library 这张真实的图。"""

from __future__ import annotations

import pytest

from examples.library.app import LibraryApp
from examples.library.repositories import BookRepository
from examples.library.services import LibraryService

pytestmark = pytest.mark.functional


async def test_the_example_graph_comes_up_serves_and_reclaims() -> None:
    async with LibraryApp() as app:
        service = app.library

        assert service.books.database is service.loans.database
        assert service.search("三体") == ["三体"]
        assert "借出《三体》" in service.borrow(1, 1)
        assert _stock(service, 1) == 2
        assert "归还《三体》" in service.return_book(1)
        assert _stock(service, 1) == 3


def _stock(service: LibraryService, book_id: int) -> int:
    book = service.books.get(book_id)
    assert book is not None
    return int(book["stock"])


async def test_any_unit_can_be_the_entry_point() -> None:
    async with BookRepository() as books:
        assert [b["title"] for b in books.search("活着")] == ["活着"]
