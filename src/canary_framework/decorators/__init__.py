"""Decorator API — ``@service``, ``@module``, lifecycle hooks, and ``@config``."""

from canary_framework.decorators.config import config
from canary_framework.decorators.module import module
from canary_framework.decorators.service import service

__all__ = [
    "config",
    "module",
    "service",
]
