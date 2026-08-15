"""Database —— 内存数据库单元：建表 + 造一批模拟数据。"""

from canary_framework import cocoa, on_init, on_start, on_stop

from .config import Config


@cocoa(deps=[Config])
class Database:
    @on_init
    def create_tables(self) -> None:
        self.tables = {
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

    @on_start
    def connect(self) -> None:
        print(f"  [Database] 连接 {self.config.settings['db_name']}")

    @on_stop
    def close(self) -> None:
        print("  [Database] 断开连接")
