"""
@web 装饰器 —— 将服务或模块标记为 Web 端点。

@web 用于标记哪些服务/模块需要注册 FastAPI 路由，并声明其使用的路由类。

与 @router 的关系：
    @web(routers=[UserRouter])  —— 当前服务/模块使用 UserRouter 路由类
    @router(prefix="/api")      —— UserRouter 是一个路由类，指定 URL 前缀

如果一个类既有 @web(routers=[...]) 又有 @module，则：
    - 注册 routrs 中每个路由类的 HTTP 方法
    - 如果该类自身也有 @get/@post 等方法，也会一起注册
"""
from __future__ import annotations

# 标记属性名：标识该类被 @web 装饰过
_CF_WEB_ATTR     = "__cf_web__"
# 标记属性名：存储 @web(routers=[...]) 中声明的路由类列表
_CF_WEB_ROUTERS  = "__cf_web_routers__"


def web(routers: list[type] | None = None):
    """
    标记一个类为 Web 端点，并声明其路由类。

    参数：
        routers: （可选）路由类列表，每个类必须被 @router 装饰
                 例如：routers=[UserRouter, AdminRouter]

    使用方式：
        @web(routers=[UserRouter])
        @service(name="UserService", config=UserConfig, deps=[DBService])
        class UserService:
            ...

    注意：
        @web 必须放在 @service/@module 之上（外层），因为
        @service/@module 需要在注册时保留元数据，@web 装饰器可能会改变类
    """
    _routers = routers or []

    def decorator(cls: type) -> type:
        # 在类上设置 web 标记和路由类列表
        setattr(cls, _CF_WEB_ATTR, True)
        setattr(cls, _CF_WEB_ROUTERS, _routers)
        return cls

    return decorator


def is_web(cls: type) -> bool:
    """
    判断一个类是否被 @web 装饰过。

    参数：
        cls: 要检查的类

    返回值：
        True 如果该类被 @web 标记，否则 False
    """
    return bool(getattr(cls, _CF_WEB_ATTR, False))


def get_web_routers(cls: type) -> list[type]:
    """
    获取 @web(routers=[...]) 中声明的路由类列表。

    参数：
        cls: 被 @web 装饰的类

    返回值：
        路由类列表，如果没有声明则返回空列表
    """
    return getattr(cls, _CF_WEB_ROUTERS, [])
