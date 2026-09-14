"""MemberRepository —— 读者数据访问。"""

from canary_framework import Canary, dep

from ..database import Database, Row


class MemberRepository(Canary):
    database = dep(Database)

    def get(self, member_id: int) -> Row | None:
        return next((m for m in self.database.tables["members"] if m["id"] == member_id), None)
