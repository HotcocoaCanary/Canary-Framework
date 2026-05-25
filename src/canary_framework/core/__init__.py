"""Core module — decorators, engine, registry, and utilities.

Public API:
    - Decorators:  :func:`config`, :func:`service`, :func:`module`,
      :func:`on_init`, :func:`on_start`, :func:`on_end`
    - Engine:      :class:`Canary`, :class:`Context`
"""

from canary_framework.core.decorators.config import config
from canary_framework.core.decorators.lifecycle import (
    LifecycleHook,
    on_end,
    on_init,
    on_start,
)
from canary_framework.core.decorators.module import module
from canary_framework.core.decorators.service import service
from canary_framework.core.engine.canary import Canary
from canary_framework.core.engine.context import Context

__all__ = [
    "Canary",
    "Context",
    "LifecycleHook",
    "config",
    "module",
    "on_end",
    "on_init",
    "on_start",
    "service",
]
