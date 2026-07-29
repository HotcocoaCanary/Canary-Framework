"""Functional request binding through route collection and Assembly compilation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field
from starlette.testclient import TestClient

from canary_framework.common import ASGIApp, CanaryConfig, RouteContext
from canary_framework.core import RouterBase
from canary_framework.decorators import get, patch, router
from canary_framework.engine.assembly import compile_assembly

pytestmark = pytest.mark.functional


class PatchBody(BaseModel):
    """User update body."""

    name: str


@router(prefix="/api")
class BindingRouter(RouterBase):
    """Real declaration owner used by binding integration tests."""

    @patch(
        "/users/{user_id}?notify={notify}",
        request_model=PatchBody,
        status_code=202,
    )
    async def update(
        self,
        user_id: int,
        notify: bool,
        body: PatchBody,
    ) -> dict[str, object]:
        return {"user_id": user_id, "name": body.name, "notify": notify}

    @get("/search?limit={limit}&query={query}")
    async def search(
        self,
        limit: int | None = None,
        query: str = Field("none", description="search term"),
    ) -> dict[str, object]:
        return {"limit": limit, "query": query}

    @get("/feature?flag={flag}")
    async def feature(self, flag: bool) -> dict[str, bool]:
        return {"flag": flag}

    @get("/failure")
    async def failure(self) -> object:
        raise ValueError("domain failure")


def binding_app() -> ASGIApp:
    """Compile one real router through the fixed Assembly pipeline."""
    routes = BindingRouter()._collect_routes(RouteContext())
    return compile_assembly(routes, config=CanaryConfig()).asgi_app


def test_path_query_and_body_bind_by_analyzed_names() -> None:
    with TestClient(binding_app()) as client:
        response = client.patch(
            "/api/users/7?notify=true",
            json={"name": "Ada"},
        )

    assert response.status_code == 202
    assert response.json() == {"user_id": 7, "name": "Ada", "notify": True}


def test_malformed_json_is_400_and_binding_validation_is_422() -> None:
    with TestClient(binding_app()) as client:
        assert client.patch("/api/users/7?notify=true", content="{").status_code == 400
        assert client.patch("/api/users/7?notify=true", json={}).status_code == 422
        assert (
            client.patch(
                "/api/users/not-an-int?notify=true",
                json={"name": "Ada"},
            ).status_code
            == 422
        )
        assert client.patch("/api/users/7", json={"name": "Ada"}).status_code == 422


def test_optional_scalar_and_field_defaults_are_preserved() -> None:
    with TestClient(binding_app()) as client:
        assert client.get("/api/search").json() == {"limit": None, "query": "none"}
        assert client.get("/api/search?limit=4&query=canary").json() == {
            "limit": 4,
            "query": "canary",
        }


def test_bool_query_accepts_common_spellings_and_rejects_unknown_values() -> None:
    with TestClient(binding_app()) as client:
        for value in ("true", "TRUE", "1", "yes", "on"):
            assert client.get(f"/api/feature?flag={value}").json() == {"flag": True}
        for value in ("false", "FALSE", "0", "no", "off"):
            assert client.get(f"/api/feature?flag={value}").json() == {"flag": False}
        assert client.get("/api/feature?flag=unknown").status_code == 422
        assert client.get("/api/feature").status_code == 422


def test_domain_value_error_is_not_rewritten_as_binding_validation() -> None:
    with (
        TestClient(binding_app()) as client,
        pytest.raises(ValueError, match="domain failure"),
    ):
        client.get("/api/failure")
