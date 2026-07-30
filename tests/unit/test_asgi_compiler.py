"""Unit tests for ASGI compilation from validated route analysis."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, cast

import pytest
from pydantic import BaseModel
from starlette.responses import Response
from starlette.testclient import TestClient

from canary_framework.common import ASGIApp, CanaryConfig, RouteSpec
from canary_framework.common.routing import ResolvedRoute
from canary_framework.engine.asgi import ASGICompiler
from canary_framework.engine.openapi import OpenAPICompiler
from canary_framework.engine.validation import ValidatedRoute, validate_routes

pytestmark = pytest.mark.unit


class Owner:
    """Minimal owner for stable route identities."""

    route_specs: tuple[RouteSpec, ...] = ()


class UpdateBody(BaseModel):
    """Request body for update binding tests."""

    name: str


class Profile(BaseModel):
    """Nested response model."""

    name: str


class Envelope(BaseModel):
    """Response model containing another Pydantic model."""

    profile: Profile


class DocumentedResponse(BaseModel):
    """Response shape declared only for OpenAPI documentation."""

    documented: str


class DocsConfig(CanaryConfig):
    """Custom paths and assets for documentation route tests."""

    docs_openapi_path: str = "/schema.json"
    docs_swagger_path: str = "/reference"
    docs_redoc_path: str = "/reference/redoc"
    docs_swagger_css_cdn: str = "https://assets.example.test/swagger.css"
    docs_swagger_js_cdn: str = "https://assets.example.test/swagger.js"
    docs_redoc_cdn: str = "https://assets.example.test/redoc.js"


def resolved_route(
    handler: Callable[..., Awaitable[object]],
    *,
    method: str = "GET",
    path: str = "/items",
    request_model: type | None = None,
    response_model: type | None = None,
    status_code: int = 200,
    operation_id: str | None = None,
) -> ResolvedRoute:
    """Build an immutable resolved route around a real async handler."""
    spec = RouteSpec(
        method=method,
        local_path=path,
        handler_name=handler.__name__,
        request_model=request_model,
        response_model=response_model,
        status_code=status_code,
        operation_id=operation_id,
    )
    return ResolvedRoute(
        owner=Owner(),
        method=method,
        full_path=path,
        handler=handler,
        spec=spec,
    )


def validated(
    *routes: ResolvedRoute,
    config: CanaryConfig | None = None,
) -> tuple[ValidatedRoute, ...]:
    """Validate routes using the same canonical analysis as production assembly."""
    return validate_routes(tuple(routes), config or CanaryConfig())


def compile_test_app(
    *routes: ResolvedRoute,
    config: CanaryConfig | None = None,
    openapi: dict[str, object] | None = None,
) -> ASGIApp:
    """Compile validated routes into a directly testable Starlette router."""
    root_config = config or CanaryConfig()
    compiled_routes = validated(*routes, config=root_config)
    document = (
        OpenAPICompiler().compile(compiled_routes, config=root_config)
        if openapi is None
        else openapi
    )
    return ASGICompiler().compile(compiled_routes, openapi=document, config=root_config)


async def update_handler(user_id: int, notify: bool, body: UpdateBody) -> dict[str, object]:
    return {"user_id": user_id, "name": body.name, "notify": notify}


def update_route() -> ResolvedRoute:
    return resolved_route(
        update_handler,
        method="PATCH",
        path="/users/{user_id}?notify={notify}",
        request_model=UpdateBody,
        status_code=202,
    )


def test_compiled_endpoint_binds_path_query_and_pydantic_body() -> None:
    with TestClient(compile_test_app(update_route())) as client:
        response = client.patch("/users/7?notify=true", json={"name": "Ada"})

    assert response.status_code == 202
    assert response.json() == {"user_id": 7, "name": "Ada", "notify": True}


def test_invalid_json_and_binding_validation_statuses_are_preserved() -> None:
    with TestClient(compile_test_app(update_route())) as client:
        assert client.patch("/users/7?notify=true", content="{").status_code == 400
        assert client.patch("/users/7?notify=true", json={}).status_code == 422
        assert (
            client.patch("/users/not-an-int?notify=true", json={"name": "Ada"}).status_code == 422
        )


def test_response_precedence_is_response_then_tuple_then_route_status() -> None:
    async def route_status() -> dict[str, bool]:
        return {"ok": True}

    async def tuple_status() -> tuple[dict[str, bool], int]:
        return {"ok": True}, 202

    async def explicit_response() -> Response:
        return Response(status_code=204)

    with TestClient(
        compile_test_app(
            resolved_route(
                route_status,
                path="/route-status",
                status_code=201,
                operation_id="route_status",
            ),
            resolved_route(
                tuple_status,
                path="/tuple-status",
                status_code=201,
                operation_id="tuple_status",
            ),
            resolved_route(
                explicit_response,
                path="/response-status",
                status_code=201,
                operation_id="response_status",
            ),
        )
    ) as client:
        assert client.get("/route-status").status_code == 201
        assert client.get("/tuple-status").status_code == 202
        assert client.get("/response-status").status_code == 204


@pytest.mark.asyncio
async def test_response_model_documents_schema_without_converting_handler_result() -> None:
    async def handler() -> dict[str, int]:
        return {"actual": 7}

    route = resolved_route(handler, response_model=DocumentedResponse)
    compiled = validated(route)
    document = OpenAPICompiler().compile(compiled, config=CanaryConfig())
    paths = cast("dict[str, Any]", document["paths"])
    response_schema = paths["/items"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]

    assert response_schema == {"$ref": "#/components/schemas/DocumentedResponse"}
    app = ASGICompiler().compile(compiled, openapi=document, config=CanaryConfig())
    received = False
    sent: list[MutableMapping[str, Any]] = []

    async def receive() -> dict[str, Any]:
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: MutableMapping[str, Any]) -> None:
        sent.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/items",
            "raw_path": b"/items",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        },
        receive,
        send,
    )
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 200
    assert sent[1]["body"] == b'{"actual":7}'


def test_optional_scalar_defaults_and_missing_required_query_are_bound() -> None:
    async def search(limit: int | None = None, active: bool = False) -> dict[str, object]:
        return {"limit": limit, "active": active}

    async def required(query: str) -> dict[str, str]:
        return {"query": query}

    with TestClient(
        compile_test_app(
            resolved_route(
                search,
                path="/search?limit={limit}&active={active}",
                operation_id="search",
            ),
            resolved_route(
                required,
                path="/required?query={query}",
                operation_id="required",
            ),
        )
    ) as client:
        assert client.get("/search").json() == {"limit": None, "active": False}
        assert client.get("/search?limit=3&active=on").json() == {
            "limit": 3,
            "active": True,
        }
        assert client.get("/required").status_code == 422


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "YeS"])
def test_bool_query_accepts_truthy_spellings(value: str) -> None:
    async def feature(flag: bool) -> dict[str, bool]:
        return {"flag": flag}

    with TestClient(
        compile_test_app(resolved_route(feature, path="/feature?flag={flag}"))
    ) as client:
        assert client.get(f"/feature?flag={value}").json() == {"flag": True}


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "FALSE", "No"])
def test_bool_query_accepts_falsy_spellings(value: str) -> None:
    async def feature(flag: bool) -> dict[str, bool]:
        return {"flag": flag}

    with TestClient(
        compile_test_app(resolved_route(feature, path="/feature?flag={flag}"))
    ) as client:
        assert client.get(f"/feature?flag={value}").json() == {"flag": False}


def test_pydantic_and_nested_list_dict_results_convert_to_json() -> None:
    async def nested() -> dict[str, object]:
        return {
            "envelope": Envelope(profile=Profile(name="Ada")),
            "profiles": [Profile(name="Grace")],
        }

    async def listed() -> list[object]:
        return [Profile(name="Lin"), {"nested": Profile(name="Edsger")}]

    with TestClient(
        compile_test_app(
            resolved_route(nested, path="/nested", operation_id="nested"),
            resolved_route(listed, path="/listed", operation_id="listed"),
        )
    ) as client:
        assert client.get("/nested").json() == {
            "envelope": {"profile": {"name": "Ada"}},
            "profiles": [{"name": "Grace"}],
        }
        assert client.get("/listed").json() == [
            {"name": "Lin"},
            {"nested": {"name": "Edsger"}},
        ]


def test_domain_value_error_propagates_outside_binding_boundary() -> None:
    async def failing() -> object:
        raise ValueError("domain failure")

    with (
        TestClient(compile_test_app(resolved_route(failing))) as client,
        pytest.raises(
            ValueError,
            match="domain failure",
        ),
    ):
        client.get("/items")


def test_compiler_consumes_retained_analysis_without_signature_reparse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    route = resolved_route(handler, path="/items/{item_id}")
    retained = validated(route)

    def fail_signature(*args: object, **kwargs: object) -> inspect.Signature:
        del args, kwargs
        raise AssertionError("handler signature was re-parsed")

    monkeypatch.setattr(inspect, "signature", fail_signature)
    app = ASGICompiler().compile(retained, openapi={}, config=CanaryConfig())

    with TestClient(app) as client:
        assert client.get("/items/9").json() == {"item_id": 9}


def test_docs_routes_use_compiled_document_and_runtime_config() -> None:
    async def handler() -> dict[str, bool]:
        return {"ok": True}

    document: dict[str, object] = {"compiled": {"once": True}}
    app = compile_test_app(
        resolved_route(handler),
        config=DocsConfig(),
        openapi=document,
    )

    with TestClient(app) as client:
        assert client.get("/schema.json").json() == document
        swagger = client.get("/reference")
        redoc = client.get("/reference/redoc")

    assert "https://assets.example.test/swagger.css" in swagger.text
    assert "https://assets.example.test/swagger.js" in swagger.text
    assert 'url: "/schema.json"' in swagger.text
    assert "https://assets.example.test/redoc.js" in redoc.text
    assert 'Redoc.init("/schema.json"' in redoc.text


def test_empty_compiler_has_no_documentation_routes() -> None:
    with TestClient(compile_test_app()) as client:
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
