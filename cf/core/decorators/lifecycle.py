from __future__ import annotations

from typing import Any, Callable

_CF_ON_INIT  = "__cf_on_init__"
_CF_ON_START = "__cf_on_start__"
_CF_ON_END   = "__cf_on_end__"


def on_init(fn: Callable[..., Any]) -> Callable[..., Any]:
    setattr(fn, _CF_ON_INIT, True)
    return fn


def on_start(fn: Callable[..., Any]) -> Callable[..., Any]:
    setattr(fn, _CF_ON_START, True)
    return fn


def on_end(fn: Callable[..., Any]) -> Callable[..., Any]:
    setattr(fn, _CF_ON_END, True)
    return fn


def find_hooks(instance: object) -> dict[str, Callable[..., Any] | None]:
    hooks: dict[str, Callable[..., Any] | None] = {
        "on_init": None,
        "on_start": None,
        "on_end": None,
    }
    for attr_name in dir(instance):
        try:
            attr = getattr(instance, attr_name)
        except Exception:
            continue
        if not callable(attr):
            continue
        if getattr(attr, _CF_ON_INIT, False):
            hooks["on_init"] = attr
        elif getattr(attr, _CF_ON_START, False):
            hooks["on_start"] = attr
        elif getattr(attr, _CF_ON_END, False):
            hooks["on_end"] = attr

    for key in ("on_init", "on_start", "on_end"):
        if hooks[key] is None:
            hooks[key] = getattr(instance, key, None)

    return hooks
