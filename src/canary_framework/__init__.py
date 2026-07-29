"""Canary Framework — lightweight decorator-driven Python async service framework."""

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
from canary_framework.decorators import (
    before_shutdown,
    before_startup,
    config,
    delete,
    get,
    module,
    patch,
    post,
    put,
    router,
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
    "ServiceNotFoundError",
    "__version__",
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
