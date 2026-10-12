"""HTTP as units: routers that are units, and a FastAPI application that is one too.

FastAPI。``canary_framework.asgi`` 的子包，建在它之上，需要 FastAPI：``pip install canary-framework[fastapi]``::

    from canary_framework import asgi, dep
    from canary_framework.asgi.fastapi import App, Router, get

    class ReaderApi(Router, prefix="/readers", tags=["读者"]):
        readers = dep(ReaderService)

        @get("/{reader_id}")
        async def get(self, reader_id: int) -> Reader:
            return await self.readers.get(reader_id)

    class LibraryApi(App, title="图书馆 API"):
        readers = dep(ReaderApi)

    class Gateway(asgi.Server):
        api = dep(LibraryApi)
        port = 8010

    async with Gateway():       # 依赖按序启动，最后开始监听
        ...                     # 退出时先停止监听，再逆序回收

- :class:`Router` 是带路由的单元，``dep()`` 一个路由单元即把它挂到自己之下。
- :class:`App` 是应用单元：一个 FastAPI 应用，由依赖它的 ``asgi.Server`` 服务。
- ``get`` / ``post`` / ``put`` / ``patch`` / ``delete`` 标记方法为接口，参数解析、校验与
  OpenAPI 都交给 FastAPI。
- :func:`mount` 把一张图上的路由挂到你自己的 FastAPI 应用上——已经有应用、只想要路由单元时
  用它。

依赖方向严格单向：``app -> router -> routes``。
"""

from canary_framework.asgi.fastapi.app import App
from canary_framework.asgi.fastapi.router import Router, mount
from canary_framework.asgi.fastapi.routes import delete, get, patch, post, put

__all__ = ["App", "Router", "delete", "get", "mount", "patch", "post", "put"]
