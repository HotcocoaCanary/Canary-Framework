"""Lifecycle hook decorators and typed hook registry.

Canary Framework provides three lifecycle hooks, each represented by a
:class:`LifecycleHook` enum member:

    =========  ===================  ===================  ===================
    Hook       Decorator            Signature            Execution order
    =========  ===================  ===================  ===================
    ``INIT``   :func:`@on_init`     ``(ctx: Context)``   topological order
    ``START``  :func:`@on_start`    ``()``               topological order
    ``END``     :func:`@on_end`      ``()``               reverse topological
    =========  ===================  ===================  ===================

Hooks are **explicit opt-in**: the decorator MUST be applied for the
framework to discover the hook.  There is no fallback that matches
methods by name — this prevents accidental hook registration.

Each hook method may be ``sync`` (regular ``def``) or ``async`` (``async
def``).  The framework detects the return type at call time and adapts
accordingly.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar

_Fn = TypeVar("_Fn", bound=Callable[..., object])


class LifecycleHook(StrEnum):
    """Enumeration of valid lifecycle hook names.

    Used internally by the engine to look up hooks on service/module
    instances without string literals.
    """

    INIT = "on_init"
    """Called after DI and config loading.  Receives the service's
    :class:`~canary_framework.core.engine.context.Context` as argument."""

    START = "on_start"
    """Called in topological order during application start.  No arguments."""

    END = "on_end"
    """Called in reverse topological order during application stop.
    No arguments."""


# ---------------------------------------------------------------------------
# Private marker attributes set on decorated methods
# ---------------------------------------------------------------------------

_MARKER_MAP: dict[LifecycleHook, str] = {
    LifecycleHook.INIT: "__cf_on_init__",
    LifecycleHook.START: "__cf_on_start__",
    LifecycleHook.END: "__cf_on_end__",
}

# Inverse lookup: marker name → LifecycleHook
_MARKER_TO_HOOK: dict[str, LifecycleHook] = {v: k for k, v in _MARKER_MAP.items()}


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def on_init(fn: _Fn) -> _Fn:  # noqa: UP047
    """Mark a method as the ``on_init`` lifecycle hook.

    The decorated method receives one argument: the service's
    :class:`~canary_framework.core.engine.context.Context` instance.

    Example::

        @service(name="my-service")
        class MyService:
            @on_init
            def init(self, ctx: Context) -> None:
                db = ctx.resolve(DBService)
                self._pool = db.create_pool()

    The hook may also be ``async``::

        @on_init
        async def init(self, ctx: Context) -> None:
            self._pool = await ctx.resolve(DBService).create_pool()
    """
    setattr(fn, _MARKER_MAP[LifecycleHook.INIT], True)
    return fn


def on_start(fn: _Fn) -> _Fn:  # noqa: UP047
    """Mark a method as the ``on_start`` lifecycle hook.

    Called in topological order after all services have been initialised.
    The decorated method takes no arguments (beyond ``self``).

    Example::

        @on_start
        def start(self) -> None:
            self._server.listen()
    """
    setattr(fn, _MARKER_MAP[LifecycleHook.START], True)
    return fn


def on_end(fn: _Fn) -> _Fn:  # noqa: UP047
    """Mark a method as the ``on_end`` lifecycle hook.

    Called in **reverse** topological order during application shutdown.
    The decorated method takes no arguments (beyond ``self``).

    This is the right place to close connections, flush buffers, or
    release external resources.

    Example::

        @on_end
        def stop(self) -> None:
            self._pool.close()
    """
    setattr(fn, _MARKER_MAP[LifecycleHook.END], True)
    return fn


# ---------------------------------------------------------------------------
# Hook discovery
# ---------------------------------------------------------------------------

HookDict = dict[LifecycleHook, Callable[..., object] | None]
"""Return type of :func:`find_hooks` — a mapping from each lifecycle hook
to the bound method (or ``None`` if not defined)."""


def find_hooks(instance: object) -> HookDict:
    """Discover lifecycle hooks on a service or module instance.

    Walks the instance's MRO (via :func:`dir`) and inspects every callable
    attribute for the ``__cf_on_init__`` / ``__cf_on_start__`` /
    ``__cf_on_end__`` marker set by the decorators.

    .. important::

        Unlike earlier versions, methods are **not** matched by name.
        Only methods decorated with ``@on_init``, ``@on_start``, or
        ``@on_end`` are recognised.  This eliminates ambiguity and
        prevents accidental hook registration when a class happens
        to define a method with the same name.

    Args:
        instance: A constructed service or module instance.

    Returns:
        A :class:`HookDict` mapping each :class:`LifecycleHook` to the
        bound method, or ``None`` when the hook is not defined.

    Performance:
        Performs one ``dir()`` traversal per instance.  The result is
        cached on the ``ServiceEntry._hooks`` attribute so each instance
        is scanned at most once.
    """
    hooks: HookDict = {
        LifecycleHook.INIT: None,
        LifecycleHook.START: None,
        LifecycleHook.END: None,
    }

    for attr_name in dir(instance):
        try:
            attr = getattr(instance, attr_name)
        except Exception:
            continue
        if not callable(attr):
            continue

        for marker, hook in _MARKER_TO_HOOK.items():
            if getattr(attr, marker, False) and hooks[hook] is None:
                hooks[hook] = attr
                break
        # Short-circuit: all hooks found
        if all(v is not None for v in hooks.values()):
            break

    return hooks
