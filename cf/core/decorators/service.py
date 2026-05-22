from __future__ import annotations

from typing import Any

_CF_SERVICE_ATTR = "__cf_service__"
_CF_SERVICE_META = "__cf_service_meta__"


def service(
    name: str,
    *,
    config: type | None = None,
    deps: list[type] | None = None,
    config_file_path: str | None = None,
):
    _config = config
    _deps = deps or []
    _config_path = config_file_path

    def decorator(cls: type) -> type:
        meta = {
            "name": name,
            "deps": _deps,
            "config_cls": _config,
            "config_file_path": _config_path,
        }

        setattr(cls, _CF_SERVICE_ATTR, True)
        setattr(cls, _CF_SERVICE_META, meta)
        cls.__cf_name__ = name

        return cls

    return decorator


def is_cf_service(cls: type) -> bool:
    return bool(getattr(cls, _CF_SERVICE_ATTR, False))


def is_cf_module(cls: type) -> bool:
    return bool(getattr(cls, "_cf_module__", False))


def get_service_meta(cls: type) -> dict[str, Any]:
    return getattr(cls, _CF_SERVICE_META, {})


def get_module_meta(cls: type) -> dict[str, Any]:
    return getattr(cls, "_cf_module_meta__", {})
