"""MemberRepository —— 读者数据访问。"""

from canary_framework import cocoa

from ..database import Database


@cocoa(deps=[Database])
class MemberRepository:
    def get(self, member_id: int) -> dict | None:
        return next((m for m in self.database.tables["members"] if m["id"] == member_id), None)
