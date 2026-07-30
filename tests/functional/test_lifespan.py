"""Root-only application caching and strict lifespan behavior."""

from __future__ import annotations

from typing import Any, cast

import pytest
from starlette.testclient import TestClient

from canary_framework import get, module, router
from canary_framework.common import (
    ApplicationNotInitializedError,
    CanaryConfig,
    LifecycleState,
    RouteContext,
)
from canary_framework.core import ModuleBase, RouterBase
from canary_framework.engine.assembly import compile_assembly

pytestmark = pytest.mark.functional


@router(prefix="/items")
class ItemRouter(RouterBase):
    @get("/")
    async def list_items(self) -> dict[str, list[str]]:
        return {"items": []}


@module(children=(ItemRouter,))
class App(ModuleBase):
    pass


async def drive_lifespan(app: Any, messages: list[dict[str, str]]) -> list[dict[str, str]]:
    incoming = iter(messages)
    sent: list[dict[str, str]] = []

    async def receive() -> dict[str, str]:
        return next(incoming)

    async def send(message: dict[str, str]) -> None:
        sent.append(message)

    await app({"type": "lifespan"}, receive, send)
    return sent


@pytest.mark.asyncio
async def test_pre_init_openapi_and_asgi_access_fail() -> None:
    app = App()
    with pytest.raises(
        ApplicationNotInitializedError,
        match=r"App must be initialized with `await app\.init\(\)` before serving\.",
    ):
        app.openapi()
    with pytest.raises(ApplicationNotInitializedError):
        _ = app.asgi_app


@pytest.mark.asyncio
async def test_pre_init_lifespan_sends_startup_failed_without_init() -> None:
    app = App()
    sent = await drive_lifespan(app, [{"type": "lifespan.startup"}])
    assert sent == [
        {
            "type": "lifespan.startup.failed",
            "message": "ApplicationNotInitializedError: App must be initialized with `await app.init()` before serving.",
        }
    ]
    assert app.lifecycle_state is LifecycleState.CREATED


@pytest.mark.asyncio
async def test_initialized_lifespan_compiles_before_startup() -> None:
    app = App()
    await app.init()
    sent = await drive_lifespan(
        app,
        [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}],
    )
    assert sent == [
        {"type": "lifespan.startup.complete"},
        {"type": "lifespan.shutdown.complete"},
    ]
    assert app._assembly is not None


@pytest.mark.asyncio
async def test_parent_compilation_never_populates_child_router_assembly() -> None:
    app = App()
    await app.init()
    child = cast(RouterBase, app.direct_children[0])
    app.openapi()
    assert app._assembly is not None
    assert child._assembly is None
    with pytest.raises(ApplicationNotInitializedError, match="not a runtime root"):
        child.openapi()
    with pytest.raises(ApplicationNotInitializedError, match="not a runtime root"):
        _ = child.asgi_app


@pytest.mark.asyncio
async def test_root_assembly_is_shared_by_openapi_and_asgi() -> None:
    app = App()
    await app.init()
    first = app.openapi()
    second = app.asgi_app
    assert app._assembly is not None
    assert first is app._assembly.openapi
    assert second is app._assembly.asgi_app


@pytest.mark.asyncio
async def test_compile_conflict_fails_lifespan_before_startup() -> None:
    @router()
    class A(RouterBase):
        @get("/same")
        async def a(self) -> dict[str, str]:
            return {"a": "a"}

    @router()
    class B(RouterBase):
        @get("/same")
        async def b(self) -> dict[str, str]:
            return {"b": "b"}

    events: list[str] = []

    @module(children=(A, B))
    class Bad(ModuleBase):
        async def on_startup(self) -> None:
            events.append("startup")

    app = Bad()
    await app.init()
    sent = await drive_lifespan(app, [{"type": "lifespan.startup"}])
    assert sent[0]["type"] == "lifespan.startup.failed"
    assert "RouteCompilationError" in sent[0]["message"]
    assert events == []


@pytest.mark.asyncio
async def test_lifespan_extension_failures_send_one_terminal_message() -> None:
    @router()
    class Failing(RouterBase):
        @get("/")
        async def root(self) -> dict[str, str]:
            return {"ok": "ok"}

        async def on_startup(self) -> None:
            raise RuntimeError("boom")

    app = Failing()
    await app.init()
    sent = await drive_lifespan(app, [{"type": "lifespan.startup"}])
    assert sent == [
        {
            "type": "lifespan.startup.failed",
            "message": "LifecycleHookError: Failing.on_startup failed: boom",
        }
    ]

    @router()
    class ShutdownFailing(RouterBase):
        @get("/")
        async def root(self) -> dict[str, str]:
            return {"ok": "ok"}

        async def on_shutdown(self) -> None:
            raise RuntimeError("bye")

    app2 = ShutdownFailing()
    await app2.init()
    await app2.startup()
    sent2 = await drive_lifespan(app2, [{"type": "lifespan.shutdown"}])
    assert sent2 == [
        {
            "type": "lifespan.shutdown.failed",
            "message": "LifecycleHookError: ShutdownFailing.on_shutdown failed: bye",
        }
    ]


def test_initialized_root_delegates_http_to_cached_assembly() -> None:
    import asyncio

    app = App()
    asyncio.run(app.init())
    with TestClient(app) as client:
        response = client.get("/items")
    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert app._assembly is not None


@pytest.mark.asyncio
async def test_mounted_child_call_rejects_runtime_access() -> None:
    app = App()
    await app.init()
    child = cast(RouterBase, app.direct_children[0])

    async def receive() -> Any:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Any) -> None:
        del message

    with pytest.raises(ApplicationNotInitializedError, match="not a runtime root"):
        await child(cast(Any, {"type": "http"}), receive, send)


def test_route_less_module_has_404_and_no_docs() -> None:
    @module()
    class Empty(ModuleBase):
        pass

    app = Empty()
    import asyncio

    asyncio.run(app.init())
    assembly = compile_assembly(app._collect_routes(RouteContext()), config=CanaryConfig())
    with TestClient(assembly.asgi_app) as client:
        assert client.get("/").status_code == 404
        assert client.get("/openapi.json").status_code == 404
