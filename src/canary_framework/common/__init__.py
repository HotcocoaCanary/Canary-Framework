"""Framework-wide shared infrastructure.

Provides the type definitions, enumerations, exception classes,
and logging utilities used by all other framework modules.
"""

from canary_framework.common._logging import get_logger, init_logging, sanitize_config_values
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
    "get_logger",
    "init_logging",
    "sanitize_config_values",
]
