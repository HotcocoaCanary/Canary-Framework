"""入口：启动一个单元，它的依赖自己就位。

两种运行方式都支持::

    PYTHONPATH=src python -m examples.library.main      # 以模块运行
    python examples/library/main.py                     # 直接以脚本运行
"""

import asyncio
import sys
from pathlib import Path

# 直接以脚本运行时，把仓库根目录与 src/ 加进 sys.path，让 `examples` 包
# 与 `canary_framework` 都可被导入（`-m` 运行时 __package__ 已就位，跳过）。
if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from examples.library.app import LibraryApp
from examples.library.repositories import BookRepository


async def main() -> None:
    print("一、启动根单元：Config -> Database -> 三个仓库 -> Service -> App 自己按序起来")
    async with LibraryApp() as app:
        service = app.library
        print("   单例共享:", service.books.database is service.loans.database)
        print("\n   检索「三体」:", service.search("三体"))
        print("   ", service.borrow(1, 1))
        print("   ", service.borrow(1, 3))  # 无库存
        print("   ", service.return_book(1))
        three_body = service.books.get(1)
        print("   《三体》剩余库存:", three_body and three_body["stock"])

    print("\n二、任何单元都能自己当入口：BookRepository 连它的 Database + Config 子树")
    async with BookRepository() as books:
        print("   检索「活着」:", [b["title"] for b in books.search("活着")])


if __name__ == "__main__":
    asyncio.run(main())
