"""Web cocoa — ``@web_cocoa`` marks a class and exposes its routes at start.

web 单元：``@web_cocoa`` 把 ``@cocoa`` 单元标记为「带 HTTP 路由」——它**只打标记**，
不改造类、也不往类上注入任何东西。``Canary`` 在启动末尾按这个标记找出 web 单元，
交给 web 扩展收集路由并合并成一个统一的 Starlette 应用。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, overload

from canary_framework.common.markers import WEB_ATTR
from canary_framework.core.decorator import cocoa

_T = TypeVar("_T")

# OpenAPI 文档的默认标题与版本。它们是 ``@web_cocoa`` 的参数默认值，所以归这里；
# :mod:`~canary_framework.web.core.app` 生成文档时从这里取同一份。
_DEFAULT_TITLE = "Canary API"
_DEFAULT_VERSION = "0.1.0"


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

    等价于 ``@cocoa(deps=...)`` 再叠加一个 web 标记；``title``/``version`` 用于生成的
    OpenAPI 文档，``prefix`` 为该单元所有路由添加公共前缀。用法::

        @web_cocoa
        class API: ...

        @web_cocoa(deps=[Repo], prefix="/api", title="Library API", version="0.1.0")
        class API: ...

    ``prefix`` 是这个单元的**绝对**前缀，与它被谁依赖无关——想要 ``/api/admin`` 就写
    ``prefix="/api/admin"``。依赖关系决定启动顺序，不决定 URL 长什么样。
    """

    normalised = _normalise_prefix(prefix)

    def mark(c: type[T]) -> type[T]:
        cocoa(deps=deps)(c)  # 先打上 @cocoa 的依赖标记（就地修改 c）
        setattr(c, WEB_ATTR, {"title": title, "version": version, "prefix": normalised})
        return c

    return mark(cls) if cls is not None else mark


def _normalise_prefix(prefix: str) -> str:
    """``"api/"`` → ``"/api"``；空前缀保持为空。

    ``@get("ping")`` 早就会自动补上前导斜杠，``prefix`` 却不会——写成 ``prefix="api"``
    会一路拼成 ``"api/ping"``，最后在 Starlette 里炸出一个裸的 ``AssertionError``。
    同一个框架里两个都是"路径"的东西，不该一个宽容一个苛刻。
    """
    trimmed = prefix.strip().strip("/")
    return f"/{trimmed}" if trimmed else ""
