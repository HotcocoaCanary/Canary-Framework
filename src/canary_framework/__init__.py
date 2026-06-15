"""Canary Framework — lightweight decorator-driven Python async service framework.

Core exports:
    - Decorators: :func:`service`, :func:`module`,
      :class:`Router`
    - Lifecycle:  :class:`LifecycleHook`
    - Exceptions: :class:`CanaryFrameworkError` and subclasses
"""

from __future__ import annotations

__version__ = "0.5.1"

from canary_framework.common import (
    CanaryConfig,
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHook,
    LifecycleHookError,
    ServiceNotFoundError,
)
from canary_framework.core.router import Router
from canary_framework.decorators import (
    before_shutdown,
    before_startup,
    config,
    module,
    service,
)

__all__ = [
    "CanaryConfig",
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyInjectionError",
    "LifecycleHook",
    "LifecycleHookError",
    "Router",
    "ServiceNotFoundError",
    "__version__",
    "before_shutdown",
    "before_startup",
    "config",
    "module",
    "service",
]
