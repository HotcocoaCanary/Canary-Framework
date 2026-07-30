"""Shared runtime-root ASGI behavior and Assembly caching."""

from __future__ import annotations

from starlette.types import Receive, Scope, Send

from canary_framework.common.config import CanaryConfig
from canary_framework.common.errors import ApplicationNotInitializedError
from canary_framework.common.routing import ASGIApp, ResolvedRoute, RouteContext
from canary_framework.common.types import LifecycleState
from canary_framework.core.service import ServiceBase
from canary_framework.engine.assembly import Assembly, compile_assembly

_NOT_INITIALIZED = "App must be initialized with `await app.init()` before serving."


class _ApplicationMixin(ServiceBase):
    """Provide root-only Assembly, OpenAPI, ASGI, and lifespan behavior."""

    def __init__(self) -> None:
        super().__init__()
        self._assembly: Assembly | None = None

    def _collect_routes(self, context: RouteContext) -> tuple[ResolvedRoute, ...]:
        raise NotImplementedError

    def _runtime_config(self) -> CanaryConfig:
        config = self.config
        return config if config is not None else CanaryConfig()

    def _require_runtime_root(self) -> None:
        if self._cf_parent_registry is not None:
            raise ApplicationNotInitializedError(
                f"{type(self).__name__} is composed under a Module and is not a runtime root."
            )

    def _ensure_assembly(self) -> Assembly:
        self._require_runtime_root()
        if self.lifecycle_state not in (LifecycleState.INITIALIZED, LifecycleState.STARTED):
            raise ApplicationNotInitializedError(_NOT_INITIALIZED)
        if self._assembly is None:
            self._assembly = compile_assembly(
                self._collect_routes(RouteContext()), config=self._runtime_config()
            )
        return self._assembly

    @property
    def asgi_app(self) -> ASGIApp:
        return self._ensure_assembly().asgi_app

    def openapi(self) -> dict[str, object]:
        return self._ensure_assembly().openapi

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return
        await self.asgi_app(scope, receive, send)

    async def _handle_lifespan(self, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                if self.lifecycle_state is not LifecycleState.INITIALIZED:
                    await send(
                        {
                            "type": "lifespan.startup.failed",
                            "message": f"ApplicationNotInitializedError: {_NOT_INITIALIZED}",
                        }
                    )
                    return
                try:
                    self._ensure_assembly()
                    await self.startup()
                except Exception as exc:
                    await send(
                        {
                            "type": "lifespan.startup.failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    return
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                try:
                    await self.shutdown()
                except Exception as exc:
                    await send(
                        {
                            "type": "lifespan.shutdown.failed",
                            "message": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    return
                await send({"type": "lifespan.shutdown.complete"})
                return
