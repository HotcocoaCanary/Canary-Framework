"""Unit tests for strict dependency graph resolution."""

import pytest

from canary_framework.common.errors import (
    CircularDependencyError,
    DependencyDirectionError,
    DependencyInjectionError,
)
from canary_framework.common.types import (
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ModuleMeta,
    RouterMeta,
    ServiceMeta,
)
from canary_framework.engine.dependencies import DependencySpec, resolve_deps, topological_sort


def _mark(cls: type, meta: ServiceMeta) -> type:
    setattr(cls, CF_SERVICE_MARKER, True)
    setattr(cls, CF_SERVICE_META, meta)
    return cls


@pytest.mark.unit
def test_resolve_deps_preserves_mro_declaration_order_and_optional_targets() -> None:
    class First:
        pass

    class Second:
        pass

    _mark(First, ServiceMeta(name="First"))
    _mark(Second, ServiceMeta(name="Second"))

    class Base:
        first: First

    class Child(Base):
        second: Second | None
        ignored: str

    _mark(Child, ServiceMeta(name="Child"))

    assert resolve_deps(Child) == (
        DependencySpec("first", First),
        DependencySpec("second", Second),
    )


@pytest.mark.unit
def test_unresolved_annotation_fails_with_owner_and_attribute() -> None:
    class Broken:
        pass

    Broken.__annotations__ = {"missing": "NotDefined"}
    with pytest.raises(DependencyInjectionError, match=r"Broken.*missing.*NotDefined"):
        resolve_deps(Broken)


@pytest.mark.unit
def test_service_may_not_depend_on_router() -> None:
    class Router:
        pass

    class Service:
        pass

    _mark(Router, RouterMeta(name="Router"))
    Service.__annotations__ = {"endpoint": Router}
    _mark(Service, ServiceMeta(name="Service"))

    with pytest.raises(DependencyDirectionError, match=r"Service\.endpoint.*Router"):
        resolve_deps(Service)


@pytest.mark.unit
@pytest.mark.parametrize("target_kind", ["router", "module"])
def test_router_may_depend_only_on_service(target_kind: str) -> None:
    class Target:
        pass

    class OwnerRouter:
        pass

    target_meta: ServiceMeta
    if target_kind == "router":
        target_meta = RouterMeta(name="Target")
    else:
        target_meta = ModuleMeta(name="Target")
    _mark(Target, target_meta)
    OwnerRouter.__annotations__ = {"invalid": Target}
    _mark(OwnerRouter, RouterMeta(name="OwnerRouter"))

    with pytest.raises(DependencyDirectionError, match=r"OwnerRouter\.invalid.*Target"):
        resolve_deps(OwnerRouter)


@pytest.mark.unit
def test_topological_sort_is_stable_and_dependency_first() -> None:
    class A:
        pass

    class B:
        pass

    class C:
        pass

    class D:
        pass

    graph = {
        A: (DependencySpec("b", B),),
        B: (DependencySpec("c", C),),
        C: (),
        D: (),
    }

    assert topological_sort(graph) == (C, D, B, A)


@pytest.mark.unit
def test_cycle_error_reports_actual_edges() -> None:
    class A:
        pass

    class B:
        pass

    class C:
        pass

    graph = {
        A: (DependencySpec("b", B),),
        B: (DependencySpec("c", C),),
        C: (DependencySpec("a", A),),
    }
    with pytest.raises(CircularDependencyError, match=r"A\.b -> B\.c -> C\.a -> A"):
        topological_sort(graph)
