"""A small web framework whose routers and application are units.

Web。``canary_framework.asgi`` 的子包，建在它之上，需要 pydantic：
``pip install canary-framework[web]``::

    from canary_framework import asgi, dep
    from canary_framework.asgi.web import App, Router, get, post

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

    class Gateway(asgi.Server):
        api = dep(LibraryApi)
        port = 8010

- :class:`Router` 是带路由的单元，``dep()`` 一个路由单元即把它挂到自己之下。
- :class:`App` 是 Web 应用单元，由依赖它的 ``asgi.Server`` 服务。
- ``get`` / ``post`` / ``put`` / ``patch`` / ``delete`` 标记方法为接口。形参按名字与注解绑定：
  路径参数、``body``、:class:`Request`，其余是查询参数；校验用 pydantic。
- :class:`Response` 与 :class:`HTTPError` 用来自己决定应答；``error`` 标记应用单元上处理某类
  异常的方法。

没有依赖注入系统（依赖走 ``dep()``），没有 OpenAPI。需要它们时用
``canary_framework.asgi.fastapi``。

依赖方向严格单向：``app -> router -> binding -> routes -> http``。
"""

from canary_framework.asgi.web.app import App
from canary_framework.asgi.web.http import HTTPError, Request, Response
from canary_framework.asgi.web.router import Router
from canary_framework.asgi.web.routes import delete, error, get, patch, post, put

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
