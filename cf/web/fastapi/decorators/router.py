"""
路由装饰器 —— @router, @get, @post, @put, @delete, @patch。

@router：   将类声明为路由类，指定 URL 前缀
@get：      标记方法为 GET 请求处理器
@post：     标记方法为 POST 请求处理器
@put：      标记方法为 PUT 请求处理器
@delete：   标记方法为 DELETE 请求处理器
@patch：    标记方法为 PATCH 请求处理器

所有路由方法在被注册到 FastAPI 时，会通过 _register_instance_routes 自动
拼接 @router(prefix) 前缀和 @get(path) 路径。

命名规则：
    get    全小写，与 FastAPI 的 app.get() 风格一致，但本质是装饰器函数而非方法
    post   全小写
    put    全小写
    delete 全小写（注意与 Python 的 del 语句冲突：导入了此装饰器则不能使用 del）
    patch  全小写
"""
from __future__ import annotations

from typing import Any, Callable

# 标记属性名：标识类为 @router 装饰的路由类
_CF_ROUTER_ATTR   = "__cf_router__"
# 标记属性名：存储路由类的 URL 前缀
_CF_ROUTER_PREFIX = "__cf_router_prefix__"
# 标记属性名：标识方法被 HTTP 方法装饰器（@get/@post 等）标记
_CF_ROUTE_ATTR    = "__cf_route__"


def router(prefix: str = "", deps: list[type] | None = None):
    """
    将一个类声明为路由类。

    参数：
        prefix: URL 前缀，所有该类中定义的 HTTP 方法路径都会加上此前缀
                例如：prefix="/api/users"，则该类中 @get("/{id}") 的完整路径为 "/api/users/{id}"
        deps:   （保留参数，暂未使用）路由类的依赖列表

    使用方式：
        @router(prefix="/api/users")
        class UserRouter:
            def __init__(self, ctx: RouterContext):
                self.ctx = ctx

            @get("/")
            async def list_users(self):
                ...

            @post("/")
            async def create_user(self, user: UserCreate):
                ...
    """
    _deps = deps or []

    def decorator(cls: type) -> type:
        # 设置标记和路由前缀
        setattr(cls, _CF_ROUTER_ATTR, True)
        setattr(cls, _CF_ROUTER_PREFIX, prefix)
        setattr(cls, "__cf_router_deps__", _deps)
        return cls

    return decorator


def is_router(cls: type) -> bool:
    """
    判断一个类是否为 @router 装饰的路由类。

    参数：
        cls: 要检查的类

    返回值：
        True 如果该类被 @router 标记
    """
    return bool(getattr(cls, _CF_ROUTER_ATTR, False))


def get_router_prefix(cls: type) -> str:
    """
    获取 @router(prefix=...) 中声明的 URL 前缀。

    参数：
        cls: 被 @router 装饰的类

    返回值：
        URL 前缀字符串，未声明时返回空字符串
    """
    return getattr(cls, _CF_ROUTER_PREFIX, "")


def _make_route(method: str):
    """
    工厂函数 —— 创建指定 HTTP 方法的装饰器。

    参数：
        method: HTTP 方法名（如 "GET", "POST", "PUT", "DELETE", "PATCH"）

    返回值：
        一个两层的装饰器函数：
        - 外层：接收路径和额外参数（如 @get("/path", status_code=201)）
        - 内层：接收被装饰的方法，设置标记属性

    工作原理：
        每个被装饰的方法会被设置三个属性：
        - _CF_ROUTE_ATTR → True（标记该方法为路由方法）
        - _cf_route_method_ → HTTP 方法名（如 "GET"）
        - _cf_route_path_ → 路径（如 "/users"）
        - _cf_route_kwargs_ → 额外参数（如 status_code, response_model 等）
    """
    def decorator(path: str, **kwargs: Any):
        def inner(fn: Callable[..., Any]) -> Callable[..., Any]:
            # 设置路由方法的各种标记属性
            setattr(fn, _CF_ROUTE_ATTR, True)
            setattr(fn, "_cf_route_method_", method)
            setattr(fn, "_cf_route_path_", path)
            setattr(fn, "_cf_route_kwargs_", kwargs)
            return fn
        return inner
    return decorator


# HTTP 方法装饰器 —— 通过 _make_route 工厂创建
# 用法：@get("/users"), @post("/users", status_code=201), 等
get    = _make_route("GET")
post   = _make_route("POST")
put    = _make_route("PUT")
delete = _make_route("DELETE")
patch  = _make_route("PATCH")


def is_route_method(fn: Callable[..., Any]) -> bool:
    """
    判断一个方法是否被 HTTP 方法装饰器标记。

    参数：
        fn: 要检查的函数/方法

    返回值：
        True 如果该方法被 @get/@post/@put/@delete/@patch 装饰
    """
    return bool(getattr(fn, _CF_ROUTE_ATTR, False))


def get_route_info(fn: Callable[..., Any]) -> tuple[str, str, dict[str, Any]]:
    """
    获取路由方法的元数据信息。

    参数：
        fn: 被 HTTP 方法装饰器标记的方法

    返回值：
        三元组：(HTTP 方法名, 路径, 额外参数字典)
        例如：("GET", "/users", {"status_code": 200})
    """
    method = getattr(fn, "_cf_route_method_", "GET")
    path   = getattr(fn, "_cf_route_path_", "/")
    kwargs = getattr(fn, "_cf_route_kwargs_", {})
    return method, path, kwargs
