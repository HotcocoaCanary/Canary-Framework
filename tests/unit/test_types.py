"""Unit tests for common.types module."""

import pytest

from canary_framework.common.types import (
    LifecycleHook,
    ModuleMeta,
    ServiceEntry,
    ServiceMeta,
)


@pytest.mark.unit
class TestLifecycleHook:
    """Tests for LifecycleHook enum."""

    def test_enum_values(self) -> None:
        """Test that enum has correct values."""
        assert LifecycleHook.BEFORE_STARTUP.value == "before_startup"
        assert LifecycleHook.BEFORE_SHUTDOWN.value == "before_shutdown"

    def test_enum_iteration(self) -> None:
        """Test enum iteration."""
        values = list(LifecycleHook)
        assert len(values) == 2


@pytest.mark.unit
class TestServiceMeta:
    """Tests for ServiceMeta dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        meta = ServiceMeta(name="test")
        assert meta.name == "test"

    def test_custom_values(self) -> None:
        """Test custom values are set correctly."""
        meta = ServiceMeta(name="custom")
        assert meta.name == "custom"


@pytest.mark.unit
class TestModuleMeta:
    """Tests for ModuleMeta dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        meta = ModuleMeta(name="test")
        assert meta.name == "test"
        assert meta.services == []

    def test_custom_values(self) -> None:
        """Test custom values are set correctly."""

        class Service:
            pass

        meta = ModuleMeta(name="custom", services=[Service])
        assert meta.name == "custom"
        assert meta.services == [Service]


@pytest.mark.unit
class TestServiceEntry:
    """Tests for ServiceEntry dataclass."""

    def test_default_values(self) -> None:

        class MyClass:
            pass

        entry = ServiceEntry(cls=MyClass, name="test")
        assert entry.cls == MyClass
        assert entry.name == "test"
        assert entry.instance is None

    def test_custom_values(self) -> None:

        class MyClass:
            pass

        instance = MyClass()
        entry = ServiceEntry(cls=MyClass, name="test", instance=instance)
        assert entry.cls == MyClass
        assert entry.name == "test"
        assert entry.instance is instance


@pytest.mark.unit
def test_resolved_route_holds_full_path_and_handler() -> None:
    from canary_framework.common import ResolvedRoute, RouteInfo

    async def h() -> None: ...

    info = RouteInfo(
        handler=h, method="GET", path="/x", starlette_path="/x",
        path_params=[], query_params=[], param_meta={},
    )
    r = ResolvedRoute(full_path="/api/x", handler=h, info=info)
    assert r.full_path == "/api/x"
    assert r.info.method == "GET"
    assert r.handler is h


@pytest.mark.unit
def test_route_info_body_param_defaults_none() -> None:
    from canary_framework.common import RouteInfo

    async def h() -> None: ...

    info = RouteInfo(
        handler=h, method="POST", path="/x", starlette_path="/x",
        path_params=[], query_params=[], param_meta={},
    )
    assert info.body_param is None
