"""Web cocoa — ``@web_cocoa`` marks a class and builds its ASGI app at start.

web 单元：``@web_cocoa`` 把 ``@cocoa`` 单元标记为「带 HTTP 路由」，并注入一个
``@on_start`` 钩子，在启动阶段收集路由、组装 Starlette 应用，作为服务入口暴露给
``Canary``（见 :func:`canary_framework.web.core.app.build_web_app`）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, overload

from canary_framework.common.markers import SERVE_ATTR, WEB_ATTR
from canary_framework.core.decorator import cocoa, on_start
from canary_framework.web.core.app import _DEFAULT_TITLE, _DEFAULT_VERSION, build_web_app

_T = TypeVar("_T")

_HOOK_NAME = "_canary_build_serve_app"


@overload
def web_cocoa[T](cls: type[T]) -> type[T]: ...


@overload
def web_cocoa[T](
    cls: None = None,
    *,
    deps: list[type] | None = None,
    title: str = _DEFAULT_TITLE,
    version: str = _DEFAULT_VERSION,
) -> Callable[[type[T]], type[T]]: ...


def web_cocoa[T](
    cls: type[T] | None = None,
    *,
    deps: list[type] | None = None,
    title: str = _DEFAULT_TITLE,
    version: str = _DEFAULT_VERSION,
) -> type[T] | Callable[[type[T]], type[T]]:
    """Mark a class as both a cocoa and an HTTP route holder.

    等价于 ``@cocoa(deps=...)`` 再叠加 web 标记，并注入一个 ``@on_start`` 钩子在启动
    阶段构建服务入口（Starlette app）；``title``/``version`` 用于生成的 OpenAPI 文档。用法::

        @web_cocoa
        class API: ...

        @web_cocoa(deps=[Repo], title="Library API", version="0.1.0")
        class API: ...
    """

    def mark(c: type[T]) -> type[T]:
        cocoa(deps=deps)(c)  # 先打上 @cocoa 的依赖标记（就地修改 c）
        setattr(c, WEB_ATTR, {"title": title, "version": version})

        @on_start  # 注入启动钩子：收集路由并构建服务入口
        async def _canary_build_serve_app(self: object) -> None:
            setattr(self, SERVE_ATTR, build_web_app(self))

        setattr(c, _HOOK_NAME, _canary_build_serve_app)
        return c

    return mark(cls) if cls is not None else mark
