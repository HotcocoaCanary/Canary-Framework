"""Framework-wide shared infrastructure — types, errors, and markers."""

from canary_framework.common.errors import (
    CanaryFrameworkError,
    CircularDependencyError,
    ConfigurationError,
    DependencyInjectionError,
    LifecycleHookError,
    ServiceNotFoundError,
)
from canary_framework.common.markers import (
    CF_HOOK_MARKER_MAP,
    CF_MODULE_MARKER,
    CF_NAME_ATTR,
    CF_ROUTER_MARKER,
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ROUTE_ATTR,
    get_module_meta,
    get_service_meta,
    is_cf_module,
    is_cf_router,
    is_cf_service,
)
from canary_framework.common.types import (
    HookFunction,
    LifecycleHook,
    ModuleMeta,
    RouterMeta,
    ServiceEntry,
    ServiceMeta,
)

__all__ = [
    "CF_HOOK_MARKER_MAP",
    "CF_MODULE_MARKER",
    "CF_NAME_ATTR",
    "CF_ROUTER_MARKER",
    "CF_SERVICE_MARKER",
    "CF_SERVICE_META",
    "ROUTE_ATTR",
    "CanaryFrameworkError",
    "CircularDependencyError",
    "ConfigurationError",
    "DependencyInjectionError",
    "HookFunction",
    "LifecycleHook",
    "LifecycleHookError",
    "ModuleMeta",
    "RouterMeta",
    "ServiceEntry",
    "ServiceMeta",
    "ServiceNotFoundError",
    "get_module_meta",
    "get_service_meta",
    "is_cf_module",
    "is_cf_router",
    "is_cf_service",
]
