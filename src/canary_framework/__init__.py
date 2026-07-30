"""Canary Framework public API."""

from __future__ import annotations

__version__ = "0.6.0"

from canary_framework.common import (
    ApplicationNotInitializedError,
    CanaryConfig,
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyDirectionError,
    DependencyInjectionError,
    LifecycleHookError,
    LifecycleStateError,
    RouteCompilationError,
    ServiceNotFoundError,
)
from canary_framework.decorators import (
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
    "ApplicationNotInitializedError",
    "CanaryConfig",
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyDirectionError",
    "DependencyInjectionError",
    "LifecycleHookError",
    "LifecycleStateError",
    "RouteCompilationError",
    "ServiceNotFoundError",
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
