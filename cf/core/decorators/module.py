from __future__ import annotations

from typing import Any

from cf.core.decorators.service import is_cf_service, get_service_meta

_CF_MODULE_ATTR = "_cf_module__"
_CF_MODULE_META = "_cf_module_meta__"


def module(
    name: str,
    *,
    config: type | None = None,
    services: list[type] | None = None,
    config_file_path: str | None = None,
):
    _config = config
    _services = services or []
    _config_path = config_file_path

    def decorator(cls: type) -> type:
        for svc_cls in _services:
            if not is_cf_service(svc_cls) and not is_cf_module(svc_cls):
                raise TypeError(
                    f"@module '{name}': '{svc_cls.__name__}' is not a @service "
                    f"or @module class."
                )

        meta = {
            "name": name,
            "config_cls": _config,
            "services": _services,
            "config_file_path": _config_path,
        }

        setattr(cls, _CF_MODULE_ATTR, True)
        setattr(cls, _CF_MODULE_META, meta)
        cls.__cf_name__ = name

        return cls

    return decorator


def is_cf_module(cls: type) -> bool:
    return bool(getattr(cls, _CF_MODULE_ATTR, False))


def get_module_meta(cls: type) -> dict[str, Any]:
    return getattr(cls, _CF_MODULE_META, {})
