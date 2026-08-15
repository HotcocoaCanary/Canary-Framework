"""Config —— 全局配置单元（模拟）。"""

from canary_framework import cocoa, on_init


@cocoa
class Config:
    @on_init
    def load(self) -> None:
        self.settings = {"db_name": "library.db", "overdue_days": 30}
        print("  [Config] 加载配置")
