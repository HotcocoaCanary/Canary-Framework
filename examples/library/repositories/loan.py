"""LoanRepository —— 借阅记录访问（依赖书籍仓库与数据库）。"""

from canary_framework import cocoa

from ..database import Database
from .book import BookRepository


@cocoa(deps=[Database, BookRepository])
class LoanRepository:
    def borrow(self, member_id: int, book_id: int) -> str:
        book = self.book_repository.get(book_id)
        if book is None or book["stock"] <= 0:
            return "借阅失败：无库存"
        book["stock"] -= 1
        self.database.tables["loans"].append({"member_id": member_id, "book_id": book_id})
        return f"借出《{book['title']}》"

    def return_book(self, book_id: int) -> str:
        book = self.book_repository.get(book_id)
        loan = next(
            (row for row in self.database.tables["loans"] if row["book_id"] == book_id), None
        )
        if loan is None:
            return "归还失败：无借阅记录"
        self.database.tables["loans"].remove(loan)
        book["stock"] += 1
        return f"归还《{book['title']}》"
