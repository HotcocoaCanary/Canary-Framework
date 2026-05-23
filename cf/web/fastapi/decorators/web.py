# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

from typing import Any

# --- 标记属性名常量 ---
# __cf_web__ 标记类是否被 @web 装饰过
_CF_WEB_ATTR     = "__cf_web__"
# __cf_web_routers__ 存储 @web(routers=[...]) 中声明的路由类列表
_CF_WEB_ROUTERS  = "__cf_web_routers__"


def web(routers: list[type] | None = None):
    # 保存路由类列表（避免闭包引用后续变化）
    _routers = routers or []

    def decorator(cls: type) -> type:
        # 在类上设置 __cf_web__ = True，标记此类为 Web 端点
        setattr(cls, _CF_WEB_ATTR, True)
        # 在类上存储路由类列表，供 _register_routes 在启动时读取
        setattr(cls, _CF_WEB_ROUTERS, _routers)
        return cls

    return decorator


def is_web(cls: type) -> bool:
    # 检查类是否被 @web 装饰过
    # bool() 确保返回 True/False 而非可能为 None
    return bool(getattr(cls, _CF_WEB_ATTR, False))


def get_web_routers(cls: type) -> list[type]:
    # 获取 @web(routers=[...]) 中声明的路由类列表
    # 如果未声明，返回空列表
    return getattr(cls, _CF_WEB_ROUTERS, [])
