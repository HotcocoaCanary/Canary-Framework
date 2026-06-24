"""Canary Framework — lightweight decorator-driven Python async service framework.

Core exports:
    - Decorators: :func:`service`, :func:`module`,
      :class:`Router`

    - Exceptions: :class:`CanaryFrameworkError` and subclasses
"""

from __future__ import annotations

__version__ = "0.5.0"

from canary_framework.common import (
    CanaryConfig,
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    ServiceNotFoundError,
)
from canary_framework.core.router import Router
from canary_framework.decorators import (
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
    "Router",
    "ServiceNotFoundError",
    "__version__",
    "config",
    "module",
    "service",
]
