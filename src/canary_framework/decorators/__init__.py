"""Decorator API — ``@service``, ``@module``, ``Router``, lifecycle hooks, and ``@config``."""

from canary_framework.core.router import Router
from canary_framework.decorators.config import config
from canary_framework.decorators.lifecycle import before_shutdown, before_startup
from canary_framework.decorators.module import module
from canary_framework.decorators.service import service

__all__ = [
    "Router",
    "before_shutdown",
    "before_startup",
    "config",
    "module",
    "service",
]
