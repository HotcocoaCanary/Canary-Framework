"""入口：把 Library 服务暴露为 REST API（@web_cocoa + @get/@post）。

运行方式::

    PYTHONPATH=src python -m examples.library.web      # 以模块运行，起 uvicorn
    python examples/library/web.py                     # 直接以脚本运行
    uvicorn examples.library.web:app                   # app 本身就是 ASGI 应用

启动后访问：
    GET  /docs                    Swagger UI（交互式文档）
    GET  /redoc                   Redoc
    GET  /openapi.json            自动生成的 OpenAPI 文档
    GET  /books?q=三体            检索
    GET  /books/1                 单本详情
    POST /books/1/borrow          借阅（body: {"member_id": 1}）
"""

import sys
from pathlib import Path

# 直接以脚本运行时，把仓库根目录与 src/ 加进 sys.path（`-m` 运行时 __package__ 已就位）。
if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from pydantic import BaseModel

from canary_framework import Canary, on_start
from canary_framework.web import get, post, web_cocoa
from examples.library.repositories import BookRepository
from examples.library.services import LibraryService


class BorrowRequest(BaseModel):
    member_id: int


@web_cocoa(deps=[BookRepository, LibraryService], title="Library API", version="0.1.0")
class LibraryAPI:
    @on_start
    async def banner(self) -> None:
        print("系线")

    @get("/books/{book_id}")
    async def get_book(self, book_id: int) -> dict:
        book = self.book_repository.get(book_id)
        return book if book is not None else {"error": "book not found"}

    @get("/books")
    async def search(self, q: str = "") -> list[dict]:
        return self.book_repository.search(q)

    @post("/books/{book_id}/borrow")
    async def borrow(self, book_id: int, body: BorrowRequest) -> dict:
        return {"result": self.library_service.borrow(body.member_id, book_id)}


app = Canary(LibraryAPI)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)  # uvicorn 经 ASGI lifespan 驱动 init/start/stop
