"""Unit tests for immutable common contracts."""

from collections.abc import Mapping

import pytest

from canary_framework.common.routing import (
    ResolvedRoute,
    ResponseSpec,
    RouteContext,
    RouteSpec,
)
from canary_framework.common.types import (
    LifecycleState,
    ModuleMeta,
    RouterMeta,
    ServiceEntry,
    ServiceMeta,
    unwrap_optional,
)


@pytest.mark.unit
def test_lifecycle_state_has_all_runtime_states() -> None:
    assert tuple(LifecycleState) == (
        LifecycleState.CREATED,
        LifecycleState.INITIALIZED,
        LifecycleState.STARTED,
        LifecycleState.STOPPED,
        LifecycleState.FAILED,
    )


@pytest.mark.unit
def test_route_spec_freezes_collections() -> None:
    source = {422: ResponseSpec("Validation failed")}
    spec = RouteSpec(
        method="get",
        local_path="/items",
        handler_name="items",
        tags=["Items"],  # type: ignore[arg-type]
        responses=source,
    )
    source[500] = ResponseSpec("Server error")

    assert spec.method == "GET"
    assert spec.tags == ("Items",)
    assert isinstance(spec.responses, Mapping)
    assert tuple(spec.responses) == (422,)
    with pytest.raises(TypeError):
        spec.responses[500] = ResponseSpec("Server error")  # type: ignore[index]


@pytest.mark.unit
def test_metadata_is_frozen_and_tuple_backed() -> None:
    service_meta = ServiceMeta(name="Clock")
    router_meta = RouterMeta(name="Users", prefix="/users", tags=("Users",))
    module_meta = ModuleMeta(name="Api", children=(str,), prefix="/api")

    assert service_meta.name == "Clock"
    assert router_meta.tags == ("Users",)
    assert module_meta.children == (str,)
    with pytest.raises(AttributeError):
        router_meta.prefix = "/changed"  # type: ignore[misc]


@pytest.mark.unit
def test_service_entry_tracks_runtime_instance() -> None:
    entry = ServiceEntry(cls=str, name="text")

    entry.instance = "ready"

    assert entry.instance == "ready"


@pytest.mark.unit
def test_resolved_route_derives_operation_id() -> None:
    class Owner:
        route_specs: tuple[RouteSpec, ...] = ()

    async def handler() -> object:
        return None

    spec = RouteSpec(method="GET", local_path="/items", handler_name="items")
    route = ResolvedRoute(
        owner=Owner(),
        method="GET",
        full_path="/api/items",
        handler=handler,
        spec=spec,
    )

    assert route.operation_id == "Owner.items"


@pytest.mark.unit
def test_route_context_has_empty_immutable_defaults() -> None:
    context = RouteContext()

    assert context.prefix == ""
    assert context.tags == ()
    assert context.security == ()
    with pytest.raises(AttributeError):
        context.prefix = "/changed"  # type: ignore[misc]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (str, (str, False)),
        (str | None, (str, True)),
    ],
)
def test_unwrap_optional(annotation: object, expected: tuple[object, bool]) -> None:
    assert unwrap_optional(annotation) == expected
