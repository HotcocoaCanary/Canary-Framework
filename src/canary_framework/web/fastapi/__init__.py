"""Web FastAPI module — HTTP routing and server integration.

Public API:
    - Decorators:  :func:`web`, :func:`router`, :func:`get`, :func:`post`,
      :func:`put`, :func:`delete`, :func:`patch`
    - Engine:      :class:`WebCanary`

Requires ``pip install canary-framework[web]``.
"""

from canary_framework.web.fastapi.decorators.router import (
    delete,
    get,
    patch,
    post,
    put,
    router,
)
from canary_framework.web.fastapi.decorators.web import web
from canary_framework.web.fastapi.web_canary import WebCanary

__all__ = [
    "WebCanary",
    "delete",
    "get",
    "patch",
    "post",
    "put",
    "router",
    "web",
]
