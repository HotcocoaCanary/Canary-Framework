"""BookRepository —— 书籍数据访问。"""

from canary_framework import Canary, dep

from ..database import Database, Row


class BookRepository(Canary):
    database = dep(Database)

    def search(self, keyword: str) -> list[Row]:
        return [b for b in self.database.tables["books"] if keyword in b["title"]]

    def get(self, book_id: int) -> Row | None:
        return next((b for b in self.database.tables["books"] if b["id"] == book_id), None)
