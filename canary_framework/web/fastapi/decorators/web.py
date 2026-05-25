"""@web 装饰器 —— 标记服务/模块为 Web 端点，声明其使用的路由类。

与 @router 的关系:
    @web(routers=[UserRouter]) — 声明当前服务使用哪些路由类
    @router(prefix="/api")      — 路由类声明，定义 URL 前缀和 HTTP 方法

注册规则 (由 _register_routes 处理):
    1. 有 routers → 注册每个 Router 的方法
    2. 无 routers → 注册类自身定义的 @get/@post 方法
    3. 有 routers + @module → 同时注册 routers 和自身方法
"""

from __future__ import annotations

_CF_WEB_ATTR = "__cf_web__"  # 标记: 被 @web 装饰
_CF_WEB_ROUTERS = "__cf_web_routers__"  # 存储: 路由类列表


def web(routers: list[type] | None = None):
    """标记服务/模块为 Web 端点。

    Args:
        routers: @router 装饰的路由类列表。

    Returns:
        内层装饰器函数。
    """
    _routers = routers or []

    def decorator(cls: type) -> type:
        setattr(cls, _CF_WEB_ATTR, True)
        setattr(cls, _CF_WEB_ROUTERS, _routers)
        return cls

    return decorator


def is_web(cls: type) -> bool:
    """判断类是否被 @web 装饰过。"""
    return bool(getattr(cls, _CF_WEB_ATTR, False))


def get_web_routers(cls: type) -> list[type]:
    """获取 @web(routers=[...]) 中声明的路由类列表。"""
    return getattr(cls, _CF_WEB_ROUTERS, [])
