"""Lifecycle-only service base class.

ServiceBase owns the framework lifecycle state machine. HTTP routing and ASGI
assembly are provided by higher-level runtime components.
"""

from __future__ import annotations

import inspect
from contextlib import suppress
from typing import final

from canary_framework.common.config import CanaryConfig
from canary_framework.common.errors import LifecycleHookError, LifecycleStateError
from canary_framework.common.types import LifecycleState


class ServiceBase:
    """Base class implementing the asynchronous service lifecycle."""

    def __init__(self) -> None:
        """Initialize a service in the created state."""
        self._cf_state = LifecycleState.CREATED
        self._cf_parent_registry: object | None = None
        self._cf_config: CanaryConfig | None = None
        self._cf_rolled_back = False
        super().__init__()

    @property
    def lifecycle_state(self) -> LifecycleState:
        """Return the current lifecycle state."""
        return self._cf_state

    @property
    def config(self) -> CanaryConfig | None:
        """Return the configuration propagated by a parent module."""
        return self._cf_config

    def _require_state(self, phase: str, expected: LifecycleState) -> None:
        """Ensure a public lifecycle phase is called from its required state."""
        if self._cf_state is not expected:
            raise LifecycleStateError(
                f"{type(self).__name__}.{phase} requires state {expected.value}; "
                f"current state is {self._cf_state.value}."
            )

    async def _call_extension(self, name: str) -> None:
        """Call an async extension point and wrap failures consistently."""
        method = getattr(self, name)
        if not inspect.iscoroutinefunction(method):
            raise LifecycleHookError(f"{type(self).__name__}.{name} must be async")
        try:
            await method()
        except LifecycleHookError:
            raise
        except Exception as exc:
            raise LifecycleHookError(f"{type(self).__name__}.{name} failed: {exc}") from exc

    @final
    async def init(self) -> None:
        """Initialize this service and invoke its async extension."""
        self._require_state("init", LifecycleState.CREATED)
        try:
            await self._init()
            await self._call_extension("on_init")
        except Exception:
            self._cf_state = LifecycleState.FAILED
            await self._rollback(started=False)
            raise
        self._cf_state = LifecycleState.INITIALIZED

    @final
    async def startup(self) -> None:
        """Start this service and invoke its async extension."""
        self._require_state("startup", LifecycleState.INITIALIZED)
        try:
            await self._startup()
            await self._call_extension("on_startup")
        except Exception:
            self._cf_state = LifecycleState.FAILED
            await self._rollback(started=True)
            raise
        self._cf_state = LifecycleState.STARTED

    @final
    async def shutdown(self) -> None:
        """Stop this service after invoking its shutdown extension."""
        self._require_state("shutdown", LifecycleState.STARTED)
        try:
            await self._call_extension("on_shutdown")
            await self._shutdown()
        except Exception:
            self._cf_state = LifecycleState.FAILED
            raise
        self._cf_state = LifecycleState.STOPPED

    async def _rollback(self, *, started: bool) -> None:
        """Best-effort, idempotent cleanup after an init or startup failure."""
        if self._cf_rolled_back:
            return
        self._cf_rolled_back = True
        failed = self._cf_state is LifecycleState.FAILED
        with suppress(Exception):
            await self._call_extension("on_shutdown")
        with suppress(Exception):
            await self._rollback_phase(started=started)
        if not failed:
            self._cf_state = LifecycleState.STOPPED

    async def _rollback_phase(self, *, started: bool) -> None:
        """Clean up resources created by the failed lifecycle phase."""
        del started
        await self._shutdown()

    async def _init(self) -> None:
        """Private initialization phase for subclasses."""
        return None

    async def _startup(self) -> None:
        """Private startup phase for subclasses."""
        return None

    async def _shutdown(self) -> None:
        """Private shutdown phase for subclasses."""
        return None

    async def on_init(self) -> None:
        """Async initialization extension point for subclasses."""
        return None

    async def on_startup(self) -> None:
        """Async startup extension point for subclasses."""
        return None

    async def on_shutdown(self) -> None:
        """Async shutdown extension point for subclasses."""
        return None


__all__ = ["ServiceBase"]
