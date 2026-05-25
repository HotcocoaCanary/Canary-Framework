"""Canary Framework — lightweight decorator-driven Python service framework.

Core exports:
    - Decorators: :func:`config`, :func:`service`, :func:`module`
    - Lifecycle:  :func:`on_init`, :func:`on_start`, :func:`on_end`,
      :class:`LifecycleHook`
    - Engine:     :class:`Canary`, :class:`Context`
    - Exceptions: :class:`CanaryFrameworkError` and subclasses
"""

from __future__ import annotations

__version__ = "0.2.0"

from canary_framework.core.decorators.config import config
from canary_framework.core.decorators.lifecycle import LifecycleHook, on_end, on_init, on_start
from canary_framework.core.decorators.module import module
from canary_framework.core.decorators.service import service
from canary_framework.core.engine.canary import Canary
from canary_framework.core.engine.context import Context
from canary_framework.exceptions import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHookError,
    ServiceNotFoundError,
)

__all__ = [
    "Canary",
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "Context",
    "DependencyInjectionError",
    "LifecycleHook",
    "LifecycleHookError",
    "ServiceNotFoundError",
    "__version__",
    "config",
    "module",
    "on_end",
    "on_init",
    "on_start",
    "service",
]
