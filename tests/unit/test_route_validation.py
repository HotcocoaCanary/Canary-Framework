"""Route analysis and pre-compilation validation tests."""

from collections.abc import Awaitable, Callable
from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from pydantic import BaseModel, Field

from canary_framework.common import CanaryConfig, RouteCompilationError
from canary_framework.common.routing import ResolvedRoute, RouteSpec
from canary_framework.engine.params import analyze_route
from canary_framework.engine.validation import validate_routes


class RouteTestConfig(CanaryConfig):
    openapi_security_schemes: dict[str, dict[str, object]] = Field(
        default_factory=lambda: {"bearerAuth": {"type": "http", "scheme": "bearer"}}
    )


class Patch(BaseModel):
    name: str


class ItemRouter:
    route_specs: tuple[RouteSpec, ...] = ()


async def search(user_id: int, query: str = "") -> dict[str, Any]:
    return {"user_id": user_id, "query": query}


async def read() -> dict[str, str]:
    return {"ok": "yes"}


async def one_body(body: Patch) -> dict[str, str]:
    return {"name": body.name}


async def two_bodies(first: str, second: str) -> dict[str, str]:
    return {"first": first, "second": second}


async def no_body() -> dict[str, str]:
    return {"ok": "yes"}


async def missing(item_id: int) -> dict[str, int]:
    return {"item_id": item_id}


def resolved(
    method: str,
    path: str,
    *,
    handler: Callable[..., Awaitable[object]] = read,
    owner: object | None = None,
    request_model: type | None = None,
    operation_id: str | None = None,
    security: tuple[str, ...] = (),
) -> ResolvedRoute:
    owner = ItemRouter() if owner is None else owner
    spec = RouteSpec(
        method=method,
        local_path=path,
        handler_name=handler.__name__,
        request_model=request_model,
        operation_id=operation_id,
    )
    return ResolvedRoute(
        owner=owner, method=method, full_path=path, handler=handler, spec=spec, security=security
    )


def test_query_template_and_path_parameters_share_one_analysis() -> None:
    route = resolved("GET", "/users/{user_id}/search?q={query}", handler=search)
    analysis = analyze_route(route)

    assert analysis.starlette_path == "/users/{user_id}/search"
    assert analysis.path_params == ("user_id",)
    assert analysis.query_params == ("query",)
    assert tuple(analysis.parameters) == ("user_id", "query")
    assert analysis.parameters["query"].has_default
    assert analysis.parameters["query"].annotation is str


@pytest.mark.parametrize(
    ("routes", "message"),
    [
        ((resolved("GET", "/items"), resolved("GET", "/items")), "duplicate route GET /items"),
        (
            (
                resolved("GET", "/one", operation_id="ItemRouter.read"),
                resolved("POST", "/two", operation_id="ItemRouter.read"),
            ),
            "duplicate operationId ItemRouter.read",
        ),
        (
            (resolved("GET", "/docs"),),
            "business route GET /docs conflicts with documentation endpoint",
        ),
        (
            (resolved("GET", "/items/{item_id}", handler=read),),
            "path parameter item_id has no handler parameter",
        ),
        (
            (resolved("POST", "/items", handler=two_bodies, request_model=Patch),),
            "multiple request body declarations",
        ),
        (
            (resolved("GET", "/private", security=("bearerAuth", "missingAuth")),),
            "unknown security scheme missingAuth",
        ),
    ],
)
def test_route_conflicts_fail_before_compilation(
    routes: tuple[ResolvedRoute, ...], message: str
) -> None:
    with pytest.raises(RouteCompilationError, match=message):
        validate_routes(routes, config=RouteTestConfig())


def test_same_router_class_under_distinct_prefixes_rejects_default_operation_id() -> None:
    first = resolved("GET", "/v1/items", owner=ItemRouter())
    second = resolved("GET", "/v2/items", owner=ItemRouter())

    with pytest.raises(RouteCompilationError, match=r"duplicate operationId ItemRouter\.read"):
        validate_routes((first, second), config=RouteTestConfig())


def test_same_path_different_methods_and_root_path_are_valid() -> None:
    async def post_root() -> object:
        return None

    routes = (resolved("GET", "/"), resolved("POST", "/", handler=post_root))
    validated = validate_routes(routes, config=RouteTestConfig())

    assert tuple(route.analysis.starlette_path for route in validated) == ("/", "/")
    assert tuple(route.operation_id for route in validated) == (
        "ItemRouter.read",
        "ItemRouter.post_root",
    )


def test_slash_normalization_and_valid_single_body_parameter() -> None:
    route = resolved("POST", "//items//", handler=one_body, request_model=Patch)
    validated = validate_routes((route,), config=RouteTestConfig())

    assert validated[0].analysis.starlette_path == "/items"
    assert validated[0].analysis.body_param == "body"


def test_custom_docs_paths_normalize_duplicate_slashes_and_query_suffixes() -> None:
    class CustomDocsConfig(RouteTestConfig):
        docs_openapi_path: str = "/docs///?format={format}"
        docs_swagger_path: str = "/docs/"
        docs_redoc_path: str = "//docs?theme={theme}"

    with pytest.raises(
        RouteCompilationError,
        match="business route GET /docs conflicts with documentation endpoint",
    ):
        validate_routes((resolved("GET", "/docs"),), config=CustomDocsConfig())


def test_route_analysis_and_parameter_mapping_are_immutable() -> None:
    analysis = analyze_route(resolved("GET", "/items"))

    with pytest.raises(FrozenInstanceError):
        analysis.starlette_path = "/changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        analysis.parameters["new"] = object()  # type: ignore[index, assignment]


def test_field_default_and_metadata_are_preserved() -> None:
    async def handler(q: str = Field("x", min_length=2, description="query")) -> object:
        return q

    spec = analyze_route(resolved("GET", "/search?q={q}", handler=handler)).parameters["q"]
    assert spec.has_default
    assert spec.default is spec.field_info
    assert spec.field_info is not None
    assert spec.field_info.description == "query"


def test_untemplated_scalar_is_not_silently_treated_as_body() -> None:
    async def handler(value: str) -> object:
        return value

    with pytest.raises(RouteCompilationError, match="body parameter value requires request model"):
        validate_routes((resolved("POST", "/items", handler=handler),), config=RouteTestConfig())


def test_request_model_requires_one_body_parameter() -> None:
    with pytest.raises(
        RouteCompilationError, match="request model requires exactly one body parameter"
    ):
        validate_routes(
            (resolved("POST", "/items", handler=no_body, request_model=Patch),),
            config=RouteTestConfig(),
        )
