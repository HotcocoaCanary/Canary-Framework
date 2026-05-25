"""``@web`` decorator — marks a service/module as a Web endpoint.

声明哪些 ``@router`` 类为此服务或模块处理 HTTP 路由。

设计思路 (Design rationale):
    为什么需要 ``@web`` 而不仅靠 ``@router`` 自动发现？
    （Why ``@web`` instead of auto-discovering ``@router``?）

    1. **显式优于隐式**：服务可能导入 Router 类但不想暴露为 HTTP 端点
       Explicit is better than implicit: a service may import a Router
       class without wanting to expose it as an HTTP endpoint.
    2. **性能**：自动扫描所有类的属性来找 @router 装饰类是 O(n) 操作
       Performance: scanning all registered classes for @router would be O(n).
    3. **Router 列表在类定义时已知**，无需运行时反射
       The router list is known at class definition time.

关系 (Relationship):
    ``@web(routers=[UserRouter])``  — 声明使用哪些路由类
    ``@router(prefix="/api")``    — 路由类声明，定义 URL 前缀和 HTTP 方法

路由注册规则 (Register rules):
    1. 有 ``routers=[]`` → 注册每个 Router 的方法
    2. 无 routers + ``@module`` / ``@service`` → 注册类自身定义的 HTTP 方法
    3. 有 routers + ``@module`` → 同时注册
"""

from __future__ import annotations

from collections.abc import Callable

_WEB_ATTR = "__cf_web__"
"""Set to ``True`` on classes decorated with ``@web``."""

_WEB_ROUTERS = "__cf_web_routers__"
"""Stores the list of ``@router``-decorated classes declared via ``routers=[]``."""


def web(routers: list[type] | None = None) -> Callable[[type], type]:
    """Mark a service or module as a Web endpoint.

    标记服务/模块为 Web 端点。

    Args:
        routers: ``@router`` 装饰的路由类列表，这些类的 HTTP 方法将
                 自动注册到 FastAPI。
                 A list of ``@router``-decorated classes whose HTTP
                 methods will be registered with FastAPI.

    Returns:
        一个类装饰器。A class decorator.

    Example::

        @web(routers=[UserRouter, HealthRouter])
        @module(name="AppModule", services=[UserService])
        class AppModule:
            @get("/health")
            async def health(self) -> dict:
                return {"status": "ok"}
    """
    _routers = list(routers or ())

    def decorator(cls: type) -> type:
        setattr(cls, _WEB_ATTR, True)
        setattr(cls, _WEB_ROUTERS, _routers)
        return cls

    return decorator


def is_web(cls: type) -> bool:
    """Return ``True`` if *cls* is decorated with ``@web``.

    判断类是否被 ``@web`` 装饰过。"""
    return bool(getattr(cls, _WEB_ATTR, False))


def get_web_routers(cls: type) -> list[type]:
    """Return the list of ``@router`` classes declared via ``@web(routers=[...])``.

    获取 ``@web(routers=[...])`` 中声明的路由类列表。"""
    return getattr(cls, _WEB_ROUTERS, [])
