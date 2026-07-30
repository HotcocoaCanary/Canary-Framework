"""Lifecycle-only service base class."""

from __future__ import annotations

import inspect
from contextlib import suppress
from typing import final

from canary_framework.common.config import CanaryConfig
from canary_framework.common.errors import LifecycleHookError, LifecycleStateError
from canary_framework.common.types import LifecycleState


class ServiceBase:
    """Provide the final lifecycle state machine for every runtime node."""

    def __init__(self) -> None:
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
        """Return the configuration selected by the runtime context."""
        return self._cf_config

    def _require_state(self, phase: str, expected: LifecycleState) -> None:
        if self._cf_state is not expected:
            raise LifecycleStateError(
                f"{type(self).__name__}.{phase} requires state {expected.value}; "
                f"current state is {self._cf_state.value}."
            )

    async def _call_extension(self, name: str) -> None:
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
        """Initialize structure exactly once."""
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
        """Start initialized resources exactly once."""
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
        """Stop a started node exactly once."""
        self._require_state("shutdown", LifecycleState.STARTED)
        try:
            await self._call_extension("on_shutdown")
            await self._shutdown()
        except Exception:
            self._cf_state = LifecycleState.FAILED
            raise
        self._cf_state = LifecycleState.STOPPED

    async def _rollback(self, *, started: bool) -> None:
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
        del started
        await self._shutdown()

    async def _init(self) -> None:
        return None

    async def _startup(self) -> None:
        return None

    async def _shutdown(self) -> None:
        return None

    async def on_init(self) -> None:
        """Extend structural initialization."""
        return None

    async def on_startup(self) -> None:
        """Extend event-loop resource startup."""
        return None

    async def on_shutdown(self) -> None:
        """Extend resource shutdown."""
        return None


__all__ = ["ServiceBase"]
