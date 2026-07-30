"""Contract tests for router and HTTP method declaration decorators."""

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from canary_framework.common import (
    CanaryConfig,
    ResponseSpec,
    RouteSpec,
    get_router_meta,
    is_cf_router,
    is_cf_service,
)
from canary_framework.core import RouterBase, ServiceBase
from canary_framework.decorators import delete, get, patch, post, put, router


class RequestModel:
    pass


class ResponseModel:
    pass


@pytest.mark.unit
def test_route_decorator_preserves_handler_identity_and_signature() -> None:
    async def handler(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    decorated = get("/items/{item_id}", deprecated=True)(handler)

    assert decorated is handler
    assert decorated.__annotations__ == handler.__annotations__


@pytest.mark.unit
def test_all_http_verbs_attach_immutable_specs() -> None:
    decorators = [
        (get, "GET"),
        (post, "POST"),
        (put, "PUT"),
        (delete, "DELETE"),
        (patch, "PATCH"),
    ]

    for method_decorator, expected_method in decorators:

        async def handler() -> None:
            return None

        decorated = method_decorator("/items")(handler)
        (spec,) = decorated.__cf_handler_route_specs__  # type: ignore[attr-defined]
        assert isinstance(spec, RouteSpec)
        assert spec.method == expected_method
        assert spec.local_path == "/items"
        assert spec.handler_name == "handler"


@pytest.mark.unit
def test_route_decorator_converts_sequences_and_responses_to_immutable_values() -> None:
    declared_responses: dict[int | str, ResponseSpec] = {
        409: ResponseSpec("Conflict", ResponseModel)
    }

    async def handler() -> ResponseModel:
        return ResponseModel()

    decorated = post(
        "/items",
        request_model=RequestModel,
        response_model=ResponseModel,
        status_code=201,
        tags=["Items", "Writes"],
        summary="Create item",
        description="Creates an item.",
        deprecated=True,
        operation_id="createItem",
        responses=declared_responses,
    )(handler)

    (spec,) = decorated.__cf_handler_route_specs__  # type: ignore[attr-defined]
    assert spec.request_model is RequestModel
    assert spec.response_model is ResponseModel
    assert spec.status_code == 201
    assert spec.tags == ("Items", "Writes")
    assert spec.summary == "Create item"
    assert spec.description == "Creates an item."
    assert spec.deprecated is True
    assert spec.operation_id == "createItem"
    assert isinstance(spec.responses, MappingProxyType)
    assert spec.responses[409] == ResponseSpec("Conflict", ResponseModel)
    declared_responses[500] = ResponseSpec("Failure")
    assert 500 not in spec.responses
    with pytest.raises(TypeError):
        spec.responses[500] = ResponseSpec("Failure")  # type: ignore[index]


@router(prefix="/items", tags=("Items",), security=("bearerAuth",))
class ItemRouter(RouterBase):
    @get("/{item_id}", operation_id="readItem")
    async def read(self, item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @post("", status_code=201, responses={409: ResponseSpec("Conflict")})
    async def create(self) -> dict[str, bool]:
        return {"created": True}


@pytest.mark.unit
def test_router_collects_specs_in_declaration_order() -> None:
    assert issubclass(ItemRouter, RouterBase)
    assert issubclass(ItemRouter, ServiceBase)
    assert is_cf_service(ItemRouter)
    assert is_cf_router(ItemRouter)
    assert [spec.handler_name for spec in ItemRouter.__cf_route_specs__] == ["read", "create"]
    assert ItemRouter().route_specs is ItemRouter.__cf_route_specs__
    assert ItemRouter.__dict__["read"].__name__ == "read"


@pytest.mark.unit
def test_router_metadata_is_immutable_and_normalized() -> None:
    meta = get_router_meta(ItemRouter)
    assert meta is not None
    assert meta.name == "ItemRouter"
    assert meta.prefix == "/items"
    assert meta.tags == ("Items",)
    assert meta.security == ("bearerAuth",)
    with pytest.raises(FrozenInstanceError):
        meta.prefix = "/other"  # type: ignore[misc]


@pytest.mark.unit
def test_router_accumulates_stacked_specs_in_decorator_order() -> None:
    @router()
    class MultiMethodRouter(RouterBase):
        @post("/items")
        @get("/items")
        async def items(self) -> dict[str, bool]:
            return {"ok": True}

    assert [(spec.method, spec.handler_name) for spec in MultiMethodRouter.__cf_route_specs__] == [
        ("GET", "items"),
        ("POST", "items"),
    ]


@pytest.mark.unit
def test_router_requires_router_base() -> None:
    with pytest.raises(TypeError, match="must inherit from RouterBase"):

        @router()  # type: ignore[arg-type]
        class NotARouter(ServiceBase):
            pass


@pytest.mark.unit
def test_router_config_must_inherit_canary_config() -> None:
    with pytest.raises(TypeError, match="router config must inherit from CanaryConfig"):
        router(config=object)  # type: ignore[arg-type]

    class RouterSettings(CanaryConfig):
        pass

    @router(config=RouterSettings)
    class ConfiguredRouter(RouterBase):
        pass

    meta = get_router_meta(ConfiguredRouter)
    assert meta is not None
    assert meta.config_cls is RouterSettings
