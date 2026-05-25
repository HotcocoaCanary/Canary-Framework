"""Framework-wide shared infrastructure.

Provides the type definitions, enumerations, and exception classes
used by all other framework modules.
"""

from canary_framework.common._types import ModuleMeta, ServiceEntry, ServiceMeta
from canary_framework.common.enums import LifecycleHook
from canary_framework.common.exceptions import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHookError,
    ServiceNotFoundError,
)

__all__ = [
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyInjectionError",
    "LifecycleHook",
    "LifecycleHookError",
    "ModuleMeta",
    "ServiceEntry",
    "ServiceMeta",
    "ServiceNotFoundError",
]
