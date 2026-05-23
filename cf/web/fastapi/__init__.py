# 从 cf.web.fastapi 子模块导入所有面向用户的 Web 层 API
from cf.web.fastapi.decorators.web import web
from cf.web.fastapi.decorators.router import router, get, post, put, delete, patch
from cf.web.fastapi.web_canary import WebCanary

# RouterContext 已删除 —— 统一使用 cf.core.engine.context.Context
# 路由类构造函数接收 Context，通过 ctx.service 访问所属服务，通过 ctx.resolve() 解析依赖

__all__ = [
    "web",
    "router",
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "WebCanary",
]
