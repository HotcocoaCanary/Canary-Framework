"""入口：组装 Canary，演示 组合 / 嵌套 与 单独启动。

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

from canary_framework import Canary
from examples.library.app import LibraryApp
from examples.library.repositories import BookRepository
from examples.library.services import LibraryService


async def main() -> None:
    print("一、组合 / 嵌套：以 LibraryApp 为根，整张图按拓扑序启动")
    lib = Canary(LibraryApp)
    await lib.init()
    await lib.start()  # 启动：start
    print("   启动顺序:", [t.__name__ for t in lib.order])
    svc = lib[LibraryApp].library_service  # 懒注入
    print("   单例共享:", lib[LibraryApp].library_service is lib[LibraryService])

    print("\n   检索「三体」:", svc.search("三体"))
    print("   ", svc.borrow(1, 1))
    print("   ", svc.borrow(1, 3))  # 无库存
    print("   ", svc.return_book(1))
    print("   《三体》剩余库存:", lib[BookRepository].get(1)["stock"])
    await lib.stop()

    print("\n二、单独启动：BookRepository 自己也能飞（连它的 Database + Config 子树）")
    books = Canary(BookRepository)
    await books.init()
    await books.start()
    print("   启动顺序:", [t.__name__ for t in books.order])
    print("   检索「活着」:", [b["title"] for b in books[BookRepository].search("活着")])
    await books.stop()


if __name__ == "__main__":
    asyncio.run(main())
