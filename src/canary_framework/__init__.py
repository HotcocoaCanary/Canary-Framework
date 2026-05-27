"""Canary Framework — lightweight decorator-driven Python service framework.

Core exports:
    - Decorators: :func:`service`, :func:`module`
    - Lifecycle:  :func:`on_config`, :func:`on_init`, :func:`on_start`, :func:`on_end`,
      :class:`LifecycleHook`
    - Engine:     :class:`Canary`
    - Exceptions: :class:`CanaryFrameworkError` and subclasses
"""

from __future__ import annotations

__version__ = "0.3.1"

from canary_framework.common.enums import LifecycleHook
from canary_framework.common.exceptions import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHookError,
    ServiceNotFoundError,
)
from canary_framework.core.conductor import Canary
from canary_framework.core.decorators.lifecycle import on_config, on_end, on_init, on_start
from canary_framework.core.decorators.module import module
from canary_framework.core.decorators.service import service

__all__ = [
    "Canary",
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyInjectionError",
    "LifecycleHook",
    "LifecycleHookError",
    "ServiceNotFoundError",
    "__version__",
    "module",
    "on_config",
    "on_end",
    "on_init",
    "on_start",
    "service",
]
