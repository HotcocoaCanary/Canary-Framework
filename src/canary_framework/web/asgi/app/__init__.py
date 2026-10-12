"""Application units: a small web framework whose routers and application are units.

应用单元。需要 pydantic：``pip install canary-framework[app]``::

    from canary_framework import dep
    from canary_framework.web.asgi.app import App, Router, get, post

    class ReaderApi(Router, prefix="/readers"):
        readers = dep(ReaderService)

        @get("/{reader_id}")
        async def show(self, reader_id: int) -> Reader:
            return await self.readers.get(reader_id)

        @post(status=201)
        async def create(self, body: NewReader) -> Reader:
            return await self.readers.create(body)

    class LibraryApi(App):
        readers = dep(ReaderApi)

- :class:`App` 是应用单元，它自己就是一个 ASGI 应用：交给本包的服务器单元，或任何别的 ASGI
  服务器（``uvicorn main:app``）。
- :class:`Router` 是带路由的单元，``dep()`` 一个路由单元即把它挂到自己之下。
- ``get`` / ``post`` / ``put`` / ``patch`` / ``delete`` 标记方法为接口。形参按名字与注解绑定：
  路径参数、``body``、:class:`Request`，其余是查询参数；校验用 pydantic。
- :class:`Response` 与 :class:`HTTPError` 用来自己决定应答；``error`` 标记应用单元上处理某类
  异常的方法。

没有依赖注入系统（依赖走 ``dep()``），没有 OpenAPI。

依赖方向严格单向：``app -> router -> binding -> routes -> http``。
"""

from canary_framework.web.asgi.app.app import App
from canary_framework.web.asgi.app.http import HTTPError, Request, Response
from canary_framework.web.asgi.app.router import Router
from canary_framework.web.asgi.app.routes import delete, error, get, patch, post, put

__all__ = [
    "App",
    "HTTPError",
    "Request",
    "Response",
    "Router",
    "delete",
    "error",
    "get",
    "patch",
    "post",
    "put",
]
