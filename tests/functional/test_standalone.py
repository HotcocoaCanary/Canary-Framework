"""Standalone lifecycle behavior tests."""

from __future__ import annotations

from typing import cast

import pytest

from canary_framework import get, router, service
from canary_framework.common import RouteContext
from canary_framework.core import RouterBase, ServiceBase

pytestmark = pytest.mark.functional


@router(prefix="/health")
class HealthRouter(RouterBase):
    @get("/")
    async def health(self) -> dict[str, str]:
        return {"status": "ok"}


@service()
class PlainService(ServiceBase):
    pass


async def test_plain_service_remains_non_callable() -> None:
    subject = PlainService()
    assert not callable(subject)
    await subject.init()
    await subject.startup()
    await subject.shutdown()
    assert subject.lifecycle_state.value == "stopped"


async def test_standalone_router_is_a_runtime_root() -> None:
    subject = HealthRouter()
    await subject.init()
    routes = subject._collect_routes(RouteContext())
    assert [route.full_path for route in routes] == ["/health"]
    assert callable(subject)
    assert subject.asgi_app is not None
    assert "/health" in cast(dict[str, object], subject.openapi()["paths"])
