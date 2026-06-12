"""Framework-wide shared infrastructure — types, errors, and markers."""

from canary_framework.common.config import CF_CONFIG_MARKER, CanaryConfig
from canary_framework.common.errors import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHookError,
    ServiceNotFoundError,
)
from canary_framework.common.types import (
    CF_HOOK_MARKER_MAP,
    CF_NAME_ATTR,
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    HookFunction,
    LifecycleAware,
    LifecycleHook,
    ModuleMeta,
    RouteInfo,
    ServiceEntry,
    ServiceMeta,
    get_module_meta,
    get_service_meta,
    is_cf_module,
    is_cf_service,
)

__all__ = [
    "CF_CONFIG_MARKER",
    "CF_HOOK_MARKER_MAP",
    "CF_NAME_ATTR",
    "CF_SERVICE_MARKER",
    "CF_SERVICE_META",
    "CanaryConfig",
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyInjectionError",
    "HookFunction",
    "LifecycleAware",
    "LifecycleHook",
    "LifecycleHookError",
    "ModuleMeta",
    "RouteInfo",
    "ServiceEntry",
    "ServiceMeta",
    "ServiceNotFoundError",
    "get_module_meta",
    "get_service_meta",
    "is_cf_module",
    "is_cf_service",
]
