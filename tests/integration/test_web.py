"""Integration tests for module routing and web E2E."""

from __future__ import annotations

import warnings

with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    from starlette.testclient import TestClient

from canary_framework.decorators import get, module, router


class TestModuleWeb:
    async def test_router_asgi_app(self) -> None:
        @router()
        class ApiRouter:
            @get("/hello")
            async def hello(self, request):  # type: ignore[no-untyped-def]
                return {"message": "Hello"}

        inst = ApiRouter()
        client = TestClient(inst.asgi_app)  # type: ignore[attr-defined]
        response = client.get("/hello")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello"}

    async def test_module_mounts_routers(self) -> None:
        @router()
        class WebRouter:
            @get("/ping")
            async def ping(self, request):  # type: ignore[no-untyped-def]
                return {"pong": True}

        @module(services=[WebRouter])
        class AppModule:
            pass

        app = AppModule()
        await app.configure()  # type: ignore[attr-defined]
        await app.init()  # type: ignore[attr-defined]
        client = TestClient(app)  # type: ignore[arg-type]
        response = client.get("/WebRouterRouter/ping")
        assert response.status_code == 200
        assert response.json() == {"pong": True}
