"""Web FastAPI module — HTTP routing and server integration.

Public API:
    - Decorators:  :func:`router`, :func:`get`, :func:`post`,
      :func:`put`, :func:`delete`, :func:`patch`
    - Engine:      :class:`WebCanary`

Requires ``pip install canary-framework[web]``.
"""

from canary_framework.web.fastapi.conductor.web_canary import WebCanary
from canary_framework.web.fastapi.decorators.router import (
    delete,
    get,
    patch,
    post,
    put,
    router,
)

__all__ = [
    "WebCanary",
    "delete",
    "get",
    "patch",
    "post",
    "put",
    "router",
]
