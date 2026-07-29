"""Standalone lifecycle behavior tests."""

from __future__ import annotations

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


async def test_standalone_router_has_no_asgi_surface() -> None:
    subject = HealthRouter()
    await subject.init()
    routes = subject._collect_routes(RouteContext())
    assert [route.full_path for route in routes] == ["/health"]
    assert not callable(subject)
    assert not hasattr(subject, "asgi_app")
