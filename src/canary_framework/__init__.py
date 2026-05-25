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

from canary_framework.common.enums import LifecycleHook
from canary_framework.common.exceptions import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHookError,
    ServiceNotFoundError,
)
from canary_framework.core.conductor import Canary, Context
from canary_framework.core.decorators.config import config
from canary_framework.core.decorators.lifecycle import on_end, on_init, on_start
from canary_framework.core.decorators.module import module
from canary_framework.core.decorators.service import service

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
