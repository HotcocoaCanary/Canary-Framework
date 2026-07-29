"""Unit tests for the validated-route OpenAPI compiler."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum
from typing import Any, Literal, cast
from uuid import UUID

import pytest
from pydantic import BaseModel, Field, create_model

from canary_framework.common import CanaryConfig, ResponseSpec, RouteCompilationError, RouteSpec
from canary_framework.common.routing import ResolvedRoute
from canary_framework.engine.openapi import OpenAPICompiler
from canary_framework.engine.params import analyze_route
from canary_framework.engine.validation import ValidatedRoute


class OpenAPIConfig(CanaryConfig):
    """Root OpenAPI settings used by compiler tests."""

    openapi_title: str = "Inventory API"
    openapi_version: str = "2.1.0"
    openapi_description: str = "Inventory operations"
    openapi_servers: list[dict[str, str]] = Field(
        default_factory=lambda: [{"url": "https://api.example.test"}]
    )
    openapi_security_schemes: dict[str, dict[str, object]] = Field(
        default_factory=lambda: {
            "bearerAuth": {"type": "http", "scheme": "bearer"},
            "tenantAuth": {"type": "apiKey", "in": "header", "name": "X-Tenant"},
        }
    )


class ItemRouter:
    """Minimal route owner used to derive stable operation IDs."""

    route_specs: tuple[RouteSpec, ...] = ()


async def create() -> None:
    """Default route handler for metadata-only tests."""


def validated_route(
    *,
    method: str = "GET",
    path: str = "/items",
    handler: Any = create,
    request_model: type | None = None,
    response_model: type | None = None,
    status_code: int = 200,
    tags: tuple[str, ...] = (),
    summary: str | None = None,
    description: str | None = None,
    deprecated: bool = False,
    operation_id: str | None = None,
    responses: dict[int | str, ResponseSpec] | None = None,
    security: tuple[str, ...] = (),
) -> ValidatedRoute:
    """Build one real analysis paired with an immutable resolved route."""
    spec = RouteSpec(
        method=method,
        local_path=path,
        handler_name=handler.__name__,
        request_model=request_model,
        response_model=response_model,
        status_code=status_code,
        tags=tags,
        summary=summary,
        description=description,
        deprecated=deprecated,
        operation_id=operation_id,
        responses=responses or {},
    )
    route = ResolvedRoute(
        owner=ItemRouter(),
        method=method,
        full_path=path,
        handler=handler,
        spec=spec,
        tags=tags,
        security=security,
    )
    return ValidatedRoute(
        route=route,
        analysis=analyze_route(route),
        operation_id=route.operation_id,
    )


def validated_routes(*, response_models: tuple[type, ...]) -> tuple[ValidatedRoute, ...]:
    """Build distinct routes for a sequence of response model declarations."""
    return tuple(
        validated_route(
            path=f"/items/{index}",
            response_model=model,
            operation_id=f"ItemRouter.read_{index}",
        )
        for index, model in enumerate(response_models)
    )


def schemas(document: dict[str, object]) -> dict[str, Any]:
    """Return the compiled component schema mapping."""
    components = cast("dict[str, Any]", document["components"])
    return cast("dict[str, Any]", components["schemas"])


def operation(document: dict[str, object], path: str, method: str) -> dict[str, Any]:
    """Return one compiled operation object."""
    paths = cast("dict[str, Any]", document["paths"])
    return cast("dict[str, Any]", paths[path][method.lower()])


class Item(BaseModel):
    """Reusable response model."""

    name: str


class CanonicalBody(BaseModel):
    """Body model retained by a deliberately divergent route analysis."""

    value: str


async def canonical_handler(item_id: int, query: str, body: CanonicalBody) -> None:
    """Handler used to build canonical parameter and body analysis."""
    del item_id, query, body


def test_empty_route_tuple_returns_empty_document() -> None:
    assert OpenAPICompiler().compile((), config=OpenAPIConfig()) == {}


def test_runtime_root_config_owns_document_metadata_and_scheme_definitions() -> None:
    document = OpenAPICompiler().compile(
        (validated_route(security=("bearerAuth",)),),
        config=OpenAPIConfig(),
    )

    assert document["info"] == {
        "title": "Inventory API",
        "version": "2.1.0",
        "description": "Inventory operations",
    }
    assert document["servers"] == [{"url": "https://api.example.test"}]
    components = cast("dict[str, Any]", document["components"])
    assert components["securitySchemes"] == OpenAPIConfig().openapi_security_schemes


def test_same_model_reuses_one_component() -> None:
    document = OpenAPICompiler().compile(
        validated_routes(response_models=(Item, Item)),
        config=OpenAPIConfig(),
    )

    assert tuple(schemas(document)) == ("Item",)


def test_same_short_name_different_models_get_stable_qualified_names() -> None:
    left = create_model("Payload", value=(str, ...), __module__="tests.left")
    right = create_model("Payload", value=(int, ...), __module__="tests.right")

    document = OpenAPICompiler().compile(
        validated_routes(response_models=(left, right)),
        config=OpenAPIConfig(),
    )

    assert tuple(schemas(document)) == ("tests.left.Payload", "tests.right.Payload")


def test_nested_same_short_names_use_matching_qualified_references() -> None:
    left_payload = create_model("Payload", value=(str, ...), __module__="tests.left")
    right_payload = create_model("Payload", value=(int, ...), __module__="tests.right")
    left_envelope = create_model("Envelope", payload=(left_payload, ...), __module__="tests.left")
    right_envelope = create_model(
        "Envelope", payload=(right_payload, ...), __module__="tests.right"
    )

    document = OpenAPICompiler().compile(
        validated_routes(response_models=(left_envelope, right_envelope)),
        config=OpenAPIConfig(),
    )
    compiled = schemas(document)

    assert tuple(compiled) == (
        "tests.left.Envelope",
        "tests.left.Payload",
        "tests.right.Envelope",
        "tests.right.Payload",
    )
    assert compiled["tests.left.Envelope"]["properties"]["payload"]["$ref"] == (
        "#/components/schemas/tests.left.Payload"
    )
    assert compiled["tests.right.Envelope"]["properties"]["payload"]["$ref"] == (
        "#/components/schemas/tests.right.Payload"
    )


def test_distinct_models_with_same_qualified_name_fail_instead_of_overwriting() -> None:
    first = create_model("Payload", value=(str, ...), __module__="tests.same")
    second = create_model("Payload", value=(int, ...), __module__="tests.same")

    with pytest.raises(
        RouteCompilationError, match=r"duplicate OpenAPI schema name tests\.same\.Payload"
    ):
        OpenAPICompiler().compile(
            validated_routes(response_models=(first, second)),
            config=OpenAPIConfig(),
        )


class Envelope[T](BaseModel):
    """Generic response envelope."""

    value: T


def test_generic_component_names_are_sanitized_and_stable() -> None:
    document = OpenAPICompiler().compile(
        validated_routes(response_models=(Envelope[str], Envelope[int])),
        config=OpenAPIConfig(),
    )

    compiled = schemas(document)
    assert tuple(compiled) == ("Envelope_str", "Envelope_int")
    assert compiled["Envelope_str"]["properties"]["value"]["type"] == "string"
    assert compiled["Envelope_int"]["properties"]["value"]["type"] == "integer"
    assert operation(document, "/items/0", "GET")["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/Envelope_str"}
    assert operation(document, "/items/1", "GET")["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/Envelope_int"}


def test_separate_compiler_instances_have_isolated_complete_components() -> None:
    route = validated_route(response_model=Item)

    first = OpenAPICompiler().compile((route,), config=OpenAPIConfig())
    second = OpenAPICompiler().compile((route,), config=OpenAPIConfig())

    for document in (first, second):
        assert tuple(schemas(document)) == ("Item",)
        assert operation(document, "/items", "GET")["responses"]["200"]["content"][
            "application/json"
        ]["schema"] == {"$ref": "#/components/schemas/Item"}


def test_operation_metadata_uses_status_tags_deprecated_and_security() -> None:
    compiled = OpenAPICompiler().compile(
        (
            validated_route(
                method="POST",
                status_code=201,
                tags=("v1", "Items"),
                summary="Create item",
                description="Create one inventory item.",
                deprecated=True,
                security=("bearerAuth", "tenantAuth"),
            ),
        ),
        config=OpenAPIConfig(),
    )
    result = operation(compiled, "/items", "POST")

    assert result["operationId"] == "ItemRouter.create"
    assert result["tags"] == ["v1", "Items"]
    assert result["summary"] == "Create item"
    assert result["description"] == "Create one inventory item."
    assert result["deprecated"] is True
    assert result["security"] == [{"bearerAuth": [], "tenantAuth": []}]
    assert "201" in result["responses"]
    assert "200" not in result["responses"]


def test_parameters_path_and_request_body_come_only_from_retained_analysis() -> None:
    declared = validated_route(
        method="POST",
        path="/declared",
        operation_id="ItemRouter.declared",
    )
    canonical = validated_route(
        method="GET",
        path="/canonical/{item_id}?query={query}",
        handler=canonical_handler,
        request_model=CanonicalBody,
    )
    divergent = ValidatedRoute(
        route=declared.route,
        analysis=canonical.analysis,
        operation_id=declared.operation_id,
    )

    document = OpenAPICompiler().compile((divergent,), config=OpenAPIConfig())
    result = operation(document, "/canonical/{item_id}", "POST")

    assert [parameter["name"] for parameter in result["parameters"]] == ["item_id", "query"]
    assert result["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CanonicalBody"
    }


class State(StrEnum):
    """Query enum used to verify scalar schemas."""

    OPEN = "open"
    CLOSED = "closed"


async def scalar_parameters(
    item_id: int,
    state: State,
    mode: Literal["brief", "full"],
    created: date,
    changed: datetime,
    at: time,
    identifier: UUID,
    blob: bytes,
    maybe: int | None = None,
) -> None:
    """Handler containing every retained scalar parameter type."""


def test_parameter_schemas_preserve_enum_literal_formats_and_nullable() -> None:
    path = (
        "/items/{item_id}?state={state}&mode={mode}&created={created}&changed={changed}"
        "&at={at}&identifier={identifier}&blob={blob}&maybe={maybe}"
    )
    document = OpenAPICompiler().compile(
        (validated_route(path=path, handler=scalar_parameters),),
        config=OpenAPIConfig(),
    )
    parameters = operation(document, "/items/{item_id}", "GET")["parameters"]
    by_name = {entry["name"]: entry for entry in parameters}

    assert by_name["item_id"] == {
        "name": "item_id",
        "in": "path",
        "required": True,
        "schema": {"type": "integer"},
    }
    assert by_name["state"]["schema"] == {"type": "string", "enum": ["open", "closed"]}
    assert by_name["mode"]["schema"] == {"type": "string", "enum": ["brief", "full"]}
    assert by_name["created"]["schema"] == {"type": "string", "format": "date"}
    assert by_name["changed"]["schema"] == {"type": "string", "format": "date-time"}
    assert by_name["at"]["schema"] == {"type": "string", "format": "time"}
    assert by_name["identifier"]["schema"] == {"type": "string", "format": "uuid"}
    assert by_name["blob"]["schema"] == {"type": "string", "format": "byte"}
    assert by_name["maybe"]["required"] is False
    assert by_name["maybe"]["schema"] == {"nullable": True, "type": "integer"}


async def constrained_parameters(
    query: str = Field(
        "all",
        min_length=2,
        max_length=10,
        pattern=r"^[a-z]+$",
        title="Query",
        description="Search text",
        deprecated=True,
        examples=["item"],
    ),
    page: int = Field(1, ge=1, lt=100, multiple_of=1),
) -> None:
    """Handler containing retained Pydantic Field metadata."""


def test_parameter_schemas_preserve_field_metadata_and_constraints() -> None:
    document = OpenAPICompiler().compile(
        (
            validated_route(
                path="/search?query={query}&page={page}",
                handler=constrained_parameters,
            ),
        ),
        config=OpenAPIConfig(),
    )
    parameters = operation(document, "/search", "GET")["parameters"]
    by_name = {entry["name"]: entry for entry in parameters}

    assert by_name["query"]["required"] is False
    assert by_name["query"]["schema"] == {
        "type": "string",
        "description": "Search text",
        "title": "Query",
        "deprecated": True,
        "example": "item",
        "minLength": 2,
        "maxLength": 10,
        "pattern": r"^[a-z]+$",
    }
    assert by_name["page"]["schema"] == {
        "type": "integer",
        "minimum": 1,
        "exclusiveMaximum": 100,
        "multipleOf": 1,
    }


class Address(BaseModel):
    """Nested request component."""

    city: str


class PayloadModel(BaseModel):
    """Request component containing nested and container fields."""

    address: Address
    labels: list[str]
    attributes: dict[str, int]


async def submit(body: PayloadModel) -> None:
    """Request-model handler."""


def test_request_and_container_response_schemas_preserve_nested_models() -> None:
    route = validated_route(
        method="POST",
        handler=submit,
        request_model=PayloadModel,
        response_model=cast("type", list[PayloadModel]),
        responses={207: ResponseSpec("Mapped items", cast("type", dict[str, PayloadModel]))},
    )
    document = OpenAPICompiler().compile((route,), config=OpenAPIConfig())
    result = operation(document, "/items", "POST")
    compiled = schemas(document)

    assert result["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PayloadModel"
    }
    assert result["responses"]["200"]["content"]["application/json"]["schema"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/PayloadModel"},
    }
    assert result["responses"]["207"]["content"]["application/json"]["schema"] == {"type": "object"}
    assert compiled["PayloadModel"]["properties"]["address"]["$ref"] == (
        "#/components/schemas/Address"
    )
    assert tuple(compiled) == ("PayloadModel", "Address")


class Created(BaseModel):
    id: int


class Accepted(BaseModel):
    token: str


class Conflict(BaseModel):
    reason: str


def test_explicit_response_specs_overlay_defaults_and_keep_their_models() -> None:
    document = OpenAPICompiler().compile(
        (
            validated_route(
                method="POST",
                response_model=Created,
                status_code=201,
                responses={
                    201: ResponseSpec("Accepted instead", Accepted),
                    409: ResponseSpec("Conflict", Conflict),
                },
            ),
        ),
        config=OpenAPIConfig(),
    )
    responses = operation(document, "/items", "POST")["responses"]

    assert responses["201"] == {
        "description": "Accepted instead",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Accepted"}}},
    }
    assert responses["409"] == {
        "description": "Conflict",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Conflict"}}},
    }
    assert tuple(schemas(document)) == ("Created", "Accepted", "Conflict")


def test_route_and_http_method_declaration_order_is_preserved() -> None:
    routes = (
        validated_route(method="POST", path="/same", operation_id="ItemRouter.post"),
        validated_route(method="GET", path="/same", operation_id="ItemRouter.get"),
        validated_route(method="GET", path="/later", operation_id="ItemRouter.later"),
    )

    document = OpenAPICompiler().compile(routes, config=OpenAPIConfig())
    paths = cast("dict[str, Any]", document["paths"])

    assert tuple(paths) == ("/same", "/later")
    assert tuple(paths["/same"]) == ("post", "get")
