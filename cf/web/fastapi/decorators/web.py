from __future__ import annotations

_CF_WEB_ATTR     = "__cf_web__"
_CF_WEB_ROUTERS  = "__cf_web_routers__"


def web(routers: list[type] | None = None):
    _routers = routers or []

    def decorator(cls: type) -> type:
        setattr(cls, _CF_WEB_ATTR, True)
        setattr(cls, _CF_WEB_ROUTERS, _routers)
        return cls

    return decorator


def is_web(cls: type) -> bool:
    return bool(getattr(cls, _CF_WEB_ATTR, False))


def get_web_routers(cls: type) -> list[type]:
    return getattr(cls, _CF_WEB_ROUTERS, [])
