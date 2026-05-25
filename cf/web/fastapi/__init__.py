"""CF Web FastAPI 模块 —— FastAPI 集成。

公开 API:
    - 装饰器: web, router, get, post, put, delete, patch
    - 引擎:   WebCanary
"""

from cf.web.fastapi.decorators.router import delete, get, patch, post, put, router
from cf.web.fastapi.decorators.web import web
from cf.web.fastapi.web_canary import WebCanary

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
