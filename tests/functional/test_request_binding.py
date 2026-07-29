"""Functional coverage for the shared route-analysis binding contract.

ASGI parameter conversion remains covered by the later compiler task; these
checks ensure that compiler inputs are analyzed once and validated early.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from pydantic import BaseModel, Field

from canary_framework.common import CanaryConfig, RouteCompilationError
from canary_framework.common.routing import ResolvedRoute, RouteSpec
from canary_framework.engine.params import analyze_route
from canary_framework.engine.validation import validate_routes

pytestmark = pytest.mark.functional


class Patch(BaseModel):
    name: str


class BindingConfig(CanaryConfig):
    openapi_security_schemes: dict[str, dict[str, object]] = Field(default_factory=dict)


class Owner:
    route_specs: tuple[RouteSpec, ...] = ()


async def update_handler(user_id: int, body: Patch) -> dict[str, Any]:
    return {"user_id": user_id, "name": body.name}


async def feature_handler(flag: bool) -> dict[str, bool]:
    return {"enabled": flag}


async def search_handler(query: str = "none") -> dict[str, str]:
    return {"query": query}


def resolved(
    handler: Callable[..., Awaitable[object]],
    *,
    method: str,
    full_path: str,
    request_model: type | None = None,
    operation_id: str | None = None,
) -> ResolvedRoute:
    spec = RouteSpec(
        method=method,
        local_path=full_path,
        handler_name=handler.__name__,
        request_model=request_model,
        operation_id=operation_id,
    )
    return ResolvedRoute(
        owner=Owner(),
        method=method,
        full_path=full_path,
        handler=handler,
        spec=spec,
    )


def test_path_param_plus_body_is_analyzed_by_name() -> None:
    analysis = analyze_route(
        resolved(
            update_handler,
            method="PUT",
            full_path="/api/users/{user_id}",
            request_model=Patch,
        )
    )

    assert analysis.path_params == ("user_id",)
    assert analysis.body_param == "body"
    assert analysis.parameters["user_id"].annotation is int
    assert analysis.parameters["body"].annotation is Patch


def test_query_placeholder_without_handler_parameter_is_rejected_before_binding() -> None:
    async def handler() -> object:
        return None

    route = resolved(handler, method="GET", full_path="/api/feature?flag={flag}")
    with pytest.raises(RouteCompilationError, match="query parameter flag"):
        validate_routes((route,), config=BindingConfig())


def test_bool_query_annotation_is_preserved_for_compiler() -> None:
    analysis = analyze_route(
        resolved(feature_handler, method="GET", full_path="/api/feature?flag={flag}")
    )
    assert analysis.query_params == ("flag",)
    assert analysis.parameters["flag"].annotation is bool
    assert not analysis.parameters["flag"].has_default


def test_optional_query_default_is_preserved() -> None:
    analysis = analyze_route(
        resolved(search_handler, method="GET", full_path="/api/search?query={query}")
    )
    spec = analysis.parameters["query"]
    assert analysis.query_params == ("query",)
    assert spec.annotation is str
    assert spec.has_default
    assert spec.default == "none"


def test_field_metadata_remains_available_to_binding_and_docs() -> None:
    async def handler(query: str = Field("none", description="search term")) -> object:
        return query

    spec = analyze_route(
        resolved(handler, method="GET", full_path="/api/search?query={query}")
    ).parameters["query"]
    assert spec.field_info is not None
    assert spec.field_info.description == "search term"
