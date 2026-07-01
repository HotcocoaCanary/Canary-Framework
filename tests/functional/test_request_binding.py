"""_build_route endpoint 行为 —— 直连构造 ResolvedRoute 测试（不经装配链路）。

Direct _build_route tests: construct ResolvedRoute values and drive the
endpoint via Starlette, independent of the (not-yet-wired) assembly path.
"""

from typing import Any

import pytest
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from canary_framework.common import ResolvedRoute, RouteInfo
from canary_framework.core.router._utils import _build_route, _check_route_collisions

pytestmark = pytest.mark.functional


class Patch(BaseModel):
    name: str


async def update_handler(user_id: int, body: Patch) -> dict[str, Any]:
    return {"user_id": user_id, "name": body.name}


async def feature_handler(flag: bool) -> dict[str, Any]:
    return {"enabled": flag}


async def search_handler(query: str = "none") -> dict[str, Any]:
    return {"query": query}


def _resolved(
    handler: Any,
    *,
    method: str,
    full_path: str,
    path_params: list[str] | None = None,
    query_params: list[str] | None = None,
    param_meta: dict[str, object] | None = None,
    request_model: type | None = None,
    body_param: str | None = None,
) -> ResolvedRoute:
    info = RouteInfo(
        handler=handler,
        method=method,
        path=full_path,
        starlette_path=full_path,
        path_params=path_params or [],
        query_params=query_params or [],
        param_meta=param_meta or {},
        request_model=request_model,
        body_param=body_param,
    )
    return ResolvedRoute(full_path=full_path, handler=handler, info=info)


def _client(*routes: Route) -> TestClient:
    return TestClient(Starlette(routes=list(routes)))


def test_path_param_plus_body_binds_by_name() -> None:
    route = _build_route(
        _resolved(
            update_handler,
            method="PUT",
            full_path="/api/users/{user_id}",
            path_params=["user_id"],
            param_meta={"user_id": (int, False, None), "body": (Patch, False, None)},
            request_model=Patch,
            body_param="body",
        )
    )
    with _client(route) as c:
        r = c.put("/api/users/7", json={"name": "neo"})
        assert r.status_code == 200
        assert r.json() == {"user_id": 7, "name": "neo"}


def test_missing_required_query_returns_422() -> None:
    route = _build_route(
        _resolved(
            feature_handler,
            method="GET",
            full_path="/api/feature",
            query_params=["flag"],
            param_meta={"flag": (bool, False, None)},
        )
    )
    with _client(route) as c:
        assert c.get("/api/feature").status_code == 422


def test_bool_query_one_is_true() -> None:
    route = _build_route(
        _resolved(
            feature_handler,
            method="GET",
            full_path="/api/feature",
            query_params=["flag"],
            param_meta={"flag": (bool, False, None)},
        )
    )
    with _client(route) as c:
        assert c.get("/api/feature?flag=1").json() == {"enabled": True}


def test_optional_query_uses_default() -> None:
    route = _build_route(
        _resolved(
            search_handler,
            method="GET",
            full_path="/api/search",
            query_params=["query"],
            param_meta={"query": (str, True, None)},
        )
    )
    with _client(route) as c:
        assert c.get("/api/search").json() == {"query": "none"}


def test_check_route_collisions_raises_on_duplicate() -> None:
    r = _resolved(feature_handler, method="GET", full_path="/api/x")
    with pytest.raises(ValueError, match="collision"):
        _check_route_collisions([r, r])
