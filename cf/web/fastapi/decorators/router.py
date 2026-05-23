# 启用 PEP 563 延迟类型注解求值
from __future__ import annotations

from typing import Any, Callable

# --- 标记属性名常量 ---
# 标记类是否为 @router 装饰的路由类
_CF_ROUTER_ATTR   = "__cf_router__"
# 存储 @router(prefix="...") 声明的 URL 前缀
_CF_ROUTER_PREFIX = "__cf_router_prefix__"
# 标记方法是否为 HTTP 路由方法（被 @get/@post 等装饰过）
_CF_ROUTE_ATTR    = "__cf_route__"


def router(prefix: str = "", deps: list[type] | None = None):
    # 保存依赖列表（当前保留参数，暂未实际使用）
    _deps = deps or []

    def decorator(cls: type) -> type:
        # 在类上设置三个属性：路由标记、URL 前缀、依赖列表
        setattr(cls, _CF_ROUTER_ATTR, True)                # 标记：这是一个路由类
        setattr(cls, _CF_ROUTER_PREFIX, prefix)             # 存储 URL 前缀
        setattr(cls, "__cf_router_deps__", _deps)           # 存储（保留的）依赖列表
        return cls

    return decorator


def is_router(cls: type) -> bool:
    # 检查类是否被 @router 装饰
    return bool(getattr(cls, _CF_ROUTER_ATTR, False))


def get_router_prefix(cls: type) -> str:
    # 获取 @router(prefix="...") 声明的 URL 前缀
    # 未声明时返回空字符串 ""
    return getattr(cls, _CF_ROUTER_PREFIX, "")


# 工厂函数：根据 HTTP 方法名创建对应的路由注册装饰器
def _make_route(method: str):
    # method: HTTP 方法名字符串（如 "GET", "POST", "PUT", "DELETE", "PATCH"）

    def decorator(path: str, **kwargs: Any):
        # path: 路由路径（如 "/users", "/{id}"）
        # **kwargs: 传递给 FastAPI add_api_route 的额外参数（如 status_code, response_model 等）

        def inner(fn: Callable[..., Any]) -> Callable[..., Any]:
            # 在被装饰的函数对象上设置四个标记属性
            setattr(fn, _CF_ROUTE_ATTR, True)                 # 标记：这是一个路由处理方法
            setattr(fn, "_cf_route_method_", method)          # 存储 HTTP 方法（"GET"/"POST"/...）
            setattr(fn, "_cf_route_path_", path)              # 存储 URL 路径
            setattr(fn, "_cf_route_kwargs_", kwargs)          # 存储额外参数（传给 add_api_route）
            return fn

        return inner
    return decorator


# 使用 _make_route 工厂函数创建各 HTTP 方法的装饰器
# get("/users")     → GET    /users
# post("/users")    → POST   /users
# put("/users/1")   → PUT    /users/1
# delete("/users/1")→ DELETE /users/1
# patch("/users/1") → PATCH  /users/1
get    = _make_route("GET")
post   = _make_route("POST")
put    = _make_route("PUT")
delete = _make_route("DELETE")
patch  = _make_route("PATCH")


def is_route_method(fn: Callable[..., Any]) -> bool:
    # 检查函数是否被 @get/@post/@put/@delete/@patch 标记为路由方法
    return bool(getattr(fn, _CF_ROUTE_ATTR, False))


def get_route_info(fn: Callable[..., Any]) -> tuple[str, str, dict[str, Any]]:
    # 从被标记的函数对象上提取完整的路由信息
    # 返回三元组：(HTTP 方法名, 路径, 额外参数字典)
    method = getattr(fn, "_cf_route_method_", "GET")  # HTTP 方法，默认 GET
    path   = getattr(fn, "_cf_route_path_", "/")       # 路径，默认 "/"
    kwargs = getattr(fn, "_cf_route_kwargs_", {})       # 额外参数，默认空字典
    return method, path, kwargs
