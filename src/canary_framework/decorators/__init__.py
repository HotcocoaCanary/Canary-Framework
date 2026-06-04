"""Decorator API — ``@service``, ``@module``, ``@router``, HTTP methods, lifecycle hooks, and ``@config``."""

from canary_framework.decorators.config import config
from canary_framework.decorators.lifecycle import (
    after_config,
    after_init,
    before_shutdown,
    before_startup,
)
from canary_framework.decorators.module import module
from canary_framework.decorators.router import (
    delete,
    get,
    patch,
    post,
    put,
    router,
)
from canary_framework.decorators.service import service

__all__ = [
    "after_config",
    "after_init",
    "before_shutdown",
    "before_startup",
    "config",
    "delete",
    "get",
    "module",
    "patch",
    "post",
    "put",
    "router",
    "service",
]
