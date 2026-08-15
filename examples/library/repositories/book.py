"""BookRepository —— 书籍数据访问。"""

from canary_framework import cocoa

from ..database import Database


@cocoa(deps=[Database])
class BookRepository:
    def search(self, keyword: str) -> list[dict]:
        return [b for b in self.database.tables["books"] if keyword in b["title"]]

    def get(self, book_id: int) -> dict | None:
        return next((b for b in self.database.tables["books"] if b["id"] == book_id), None)
