"""Metadata attribute names and accessor functions.

These markers are set on classes by decorators and read by the engine.
Placing them in ``common`` is the key to avoiding circular imports.
"""

from __future__ import annotations

from .types import LifecycleHook, ModuleMeta, ServiceMeta

CF_SERVICE_MARKER = "__cf_service__"
CF_SERVICE_META = "__cf_service_meta__"
CF_MODULE_MARKER = "__cf_module__"
CF_ROUTER_MARKER = "__cf_router__"
CF_NAME_ATTR = "__cf_name__"
ROUTE_ATTR = "__cf_route__"

CF_HOOK_MARKER_MAP: dict[LifecycleHook, str] = {
    LifecycleHook.AFTER_CONFIG: "__cf_after_config__",
    LifecycleHook.AFTER_INIT: "__cf_after_init__",
    LifecycleHook.BEFORE_STARTUP: "__cf_before_startup__",
    LifecycleHook.BEFORE_SHUTDOWN: "__cf_before_shutdown__",
}


def is_cf_service(cls: type) -> bool:
    return bool(getattr(cls, CF_SERVICE_MARKER, False))


def get_service_meta(cls: type) -> ServiceMeta:
    raw = getattr(cls, CF_SERVICE_META, None)
    if isinstance(raw, ServiceMeta):
        return raw
    return ServiceMeta(name="")


def is_cf_module(cls: type) -> bool:
    return bool(getattr(cls, CF_MODULE_MARKER, False))


def get_module_meta(cls: type) -> ModuleMeta:
    raw = getattr(cls, CF_SERVICE_META, None)
    if isinstance(raw, ModuleMeta):
        return raw
    return ModuleMeta(name="")


def is_cf_router(cls: type) -> bool:
    return bool(getattr(cls, CF_ROUTER_MARKER, False))


__all__ = [
    "CF_HOOK_MARKER_MAP",
    "CF_MODULE_MARKER",
    "CF_NAME_ATTR",
    "CF_ROUTER_MARKER",
    "CF_SERVICE_MARKER",
    "CF_SERVICE_META",
    "ROUTE_ATTR",
    "get_module_meta",
    "get_service_meta",
    "is_cf_module",
    "is_cf_router",
    "is_cf_service",
]
