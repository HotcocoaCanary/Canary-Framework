"""Routers as units, and mounting them along the dependency graph.

路由单元，以及沿依赖图挂载它们。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from fastapi import APIRouter, FastAPI

from canary_framework.asgi.fastapi.routes import routes_of
from canary_framework.core import Canary, deps_of, scope_of


class Router(Canary):
    """A unit whose marked methods are endpoints, under one prefix.

    路由单元：带标记的方法是接口，类参数是它们共同的前缀与标签::

        class ReaderApi(Router, prefix="/readers", tags=["读者"]):
            readers = dep(ReaderService)

            @get("/{reader_id}")
            async def get(self, reader_id: int) -> Reader:
                return await self.readers.get(reader_id)

    聚合就是依赖：``dep()`` 一个路由单元，它就挂在自己之下，前缀逐层叠加::

        class Api(Router, prefix="/api"):
            readers = dep(ReaderApi)        # /api/readers/...
            loans = dep(LoanApi)            # /api/loans/...

    它仍是普通单元：有自己的依赖与钩子，接口方法是普通方法，测试里可以不经 HTTP 直接调用。
    它不是 FastAPI 的 ``APIRouter``，方法与属性叫什么都不会与 FastAPI 冲突。

    只有被 :class:`~canary_framework.asgi.fastapi.App` 或另一个路由单元**直接**依赖时才会被挂载；
    被两处依赖则出现在两处前缀之下。

    :param prefix: 路径前缀。
    :param tags: OpenAPI 标签。
    :param options: 原样传给 FastAPI ``APIRouter`` 的其余参数。子类继承父类的全部类参数，
        只覆盖自己写出的那些。
    """

    #: 本类的类参数，原样传给 ``APIRouter``。
    __canary_router__: ClassVar[Mapping[str, Any]] = {}

    def __init_subclass__(
        cls, *, prefix: str | None = None, tags: Sequence[str] | None = None, **options: Any
    ) -> None:
        super().__init_subclass__()
        if prefix is not None:
            options["prefix"] = prefix
        if tags is not None:
            options["tags"] = list(tags)
        cls.__canary_router__ = {**cls.__canary_router__, **options}


def mount(unit: Canary, into: FastAPI | APIRouter) -> None:
    """Add *unit*'s endpoints to *into*, then every router it depends on, recursively.

    把 *unit* 的接口加到 *into* 上，再把它直接依赖的路由单元逐个建成 ``APIRouter`` 挂上，
    递归进行。必须在 *unit* 的依赖都已就位之后调用——``@init`` 满足这一点。

    :class:`~canary_framework.asgi.fastapi.App` 自己会调用它。已经有一个 FastAPI 应用、只想要路由单元
    时直接用::

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with Library() as root:       # Library 依赖若干 Router
                mount(root, app)
                yield

    根路径在应用上写作 ``/``，因此应用自身的 ``@get`` 省略路径时即 ``/``。
    """
    top = isinstance(into, FastAPI)
    for route, endpoint in routes_of(unit):
        path = route.path or "/" if top else route.path
        into.add_api_route(path, endpoint, methods=[route.method], **route.options)
    instances = scope_of(unit).instances
    for cls in deps_of(type(unit)):
        child = instances[cls]
        if isinstance(child, Router):
            router = APIRouter(**type(child).__canary_router__)
            mount(child, router)
            into.include_router(router)
