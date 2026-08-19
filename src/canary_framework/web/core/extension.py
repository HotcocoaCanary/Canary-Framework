"""Web cocoa — ``@web_cocoa`` marks a class and exposes its routes at start.

web 单元：``@web_cocoa`` 把 ``@cocoa`` 单元标记为「带 HTTP 路由」，并注入一个
``@on_start`` 钩子，在启动阶段把路由条目收集到 ``ROUTE_ENTRIES_ATTR`` 下。``Canary``
读取这些条目、按依赖关系算出挂载前缀，合并成一个统一的 Starlette 应用。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, overload

from canary_framework.common.markers import ROUTE_ENTRIES_ATTR, WEB_ATTR
from canary_framework.core.decorator import cocoa, on_start
from canary_framework.web.core.app import _DEFAULT_TITLE, _DEFAULT_VERSION, collect_routes

_T = TypeVar("_T")

_HOOK_NAME = "_canary_collect_routes"


@overload
def web_cocoa[T](cls: type[T]) -> type[T]: ...


@overload
def web_cocoa[T](
    cls: None = None,
    *,
    deps: list[type] | None = None,
    prefix: str = "",
    title: str = _DEFAULT_TITLE,
    version: str = _DEFAULT_VERSION,
) -> Callable[[type[T]], type[T]]: ...


def web_cocoa[T](
    cls: type[T] | None = None,
    *,
    deps: list[type] | None = None,
    prefix: str = "",
    title: str = _DEFAULT_TITLE,
    version: str = _DEFAULT_VERSION,
) -> type[T] | Callable[[type[T]], type[T]]:
    """Mark a class as both a cocoa and an HTTP route holder.

    等价于 ``@cocoa(deps=...)`` 再叠加 web 标记，并注入一个 ``@on_start`` 钩子在启动
    阶段收集路由；``title``/``version`` 用于生成的 OpenAPI 文档，``prefix`` 为所有路由
    添加公共前缀。用法::

        @web_cocoa
        class API: ...

        @web_cocoa(deps=[Repo], prefix="/api", title="Library API", version="0.1.0")
        class API: ...

    ``prefix`` 会沿依赖关系逐级嵌套：``@web_cocoa(prefix="/api", deps=[AdminRouter])``
    时，``AdminRouter`` 的路由挂在 ``/api`` 之下（见
    :func:`canary_framework.runtime.mounts.mount_prefixes`）。
    """

    def mark(c: type[T]) -> type[T]:
        cocoa(deps=deps)(c)  # 先打上 @cocoa 的依赖标记（就地修改 c）
        setattr(
            c,
            WEB_ATTR,
            {"title": title, "version": version, "prefix": prefix},
        )

        @on_start  # 注入启动钩子：收集路由条目，供 Canary 合并
        async def _canary_collect_routes(self: object) -> None:
            setattr(self, ROUTE_ENTRIES_ATTR, collect_routes(self))

        setattr(c, _HOOK_NAME, _canary_collect_routes)
        return c

    return mark(cls) if cls is not None else mark
