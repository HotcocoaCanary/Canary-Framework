"""Canary Framework — lightweight decorator-driven Python async service framework.

Core exports:
    - Decorators: :func:`service`, :func:`module`, :func:`router`,
      :func:`get`, :func:`post`, :func:`put`, :func:`delete`, :func:`patch`,
      :func:`after_config`, :func:`after_init`, :func:`before_startup`, :func:`before_shutdown`
    - Lifecycle:  :class:`LifecycleHook`, :class:`RouterBase`
    - Exceptions: :class:`CanaryFrameworkError` and subclasses
"""

from __future__ import annotations

__version__ = "0.4.10"

from canary_framework.common import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHook,
    LifecycleHookError,
    ServiceNotFoundError,
)
from canary_framework.core import RouterBase
from canary_framework.decorators import (
    after_config,
    after_init,
    before_shutdown,
    before_startup,
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
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyInjectionError",
    "LifecycleHook",
    "LifecycleHookError",
    "RouterBase",
    "ServiceNotFoundError",
    "__version__",
    "after_config",
    "after_init",
    "before_shutdown",
    "before_startup",
    "delete",
    "get",
    "module",
    "patch",
    "post",
    "put",
    "router",
    "service",
]
