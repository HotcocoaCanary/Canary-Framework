"""Database —— 内存数据库单元：建表 + 造一批模拟数据。"""

from typing import Any

from canary_framework import Canary, dep, init, start, stop

from .config import Config

#: 示例用的一行记录。
Row = dict[str, Any]


class Database(Canary):
    config = dep(Config)

    @init
    def create_tables(self) -> None:
        self.tables: dict[str, list[Row]] = {
            "books": [
                {"id": 1, "title": "三体", "author": "刘慈欣", "stock": 3},
                {"id": 2, "title": "活着", "author": "余华", "stock": 1},
                {"id": 3, "title": "百年孤独", "author": "马尔克斯", "stock": 0},
            ],
            "members": [
                {"id": 1, "name": "张三"},
                {"id": 2, "name": "李四"},
            ],
            "loans": [],
        }
        print("  [Database] 建表 + 造模拟数据")

    @start
    def connect(self) -> None:
        print(f"  [Database] 连接 {self.config.settings['db_name']}")

    @stop
    def close(self) -> None:
        print("  [Database] 断开连接")
