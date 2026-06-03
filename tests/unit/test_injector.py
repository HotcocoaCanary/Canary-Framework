"""Unit tests for engine.injector module."""

import pytest

from canary_framework.common.errors import CircularDependencyError, DependencyInjectionError
from canary_framework.common.types import ServiceEntry, ServiceMeta
from canary_framework.engine.injector import inject_deps, to_snake, topological_sort
from canary_framework.engine.registry import Registry


@pytest.mark.unit
class TestToSnake:
    """Tests for to_snake function."""

    @pytest.mark.parametrize(
        "input_str, expected",
        [
            ("TestClass", "test_class"),
            ("HTTPService", "http_service"),
            ("UserService", "user_service"),
            ("APIResponse", "api_response"),
            ("Test", "test"),
            ("test", "test"),
            ("testCamel", "test_camel"),
            ("TestHTTP", "test_http"),
        ],
    )
    def test_to_snake_conversion(self, input_str: str, expected: str) -> None:
        """Test to_snake conversion for various inputs."""
        assert to_snake(input_str) == expected

    def test_empty_string(self) -> None:
        """Test empty string returns empty."""
        assert to_snake("") == ""


@pytest.mark.unit
class TestTopologicalSort:
    """Tests for topological_sort function."""

    def test_simple_dependency_chain(self) -> None:
        """Test simple dependency chain."""
        reg = Registry()

        class A:
            pass

        class B:
            pass

        class C:
            pass

        reg.register(A, meta=ServiceMeta(name="a", deps=[B]))
        reg.register(B, meta=ServiceMeta(name="b", deps=[C]))
        reg.register(C, meta=ServiceMeta(name="c", deps=[]))

        # Set up dep_names properly - these should be service names, not class names
        entries = reg.all_entries()
        for entry in entries:
            if entry.cls is A:
                entry.dep_names = ["b"]
            elif entry.cls is B:
                entry.dep_names = ["c"]
            else:
                entry.dep_names = []

        result = topological_sort(reg)
        assert result == ["c", "b", "a"]

    def test_no_dependencies(self) -> None:
        """Test services with no dependencies."""
        reg = Registry()

        class A:
            pass

        class B:
            pass

        reg.register(A, meta=ServiceMeta(name="a", deps=[]))
        reg.register(B, meta=ServiceMeta(name="b", deps=[]))

        for entry in reg.all_entries():
            entry.dep_names = []

        result = topological_sort(reg)
        assert set(result) == {"a", "b"}

    def test_circular_dependency(self) -> None:
        """Test that circular dependency raises error."""
        reg = Registry()

        class A:
            pass

        class B:
            pass

        reg.register(A, meta=ServiceMeta(name="a", deps=[B]))
        reg.register(B, meta=ServiceMeta(name="b", deps=[A]))

        for entry in reg.all_entries():
            entry.dep_names = ["b"] if entry.cls is A else ["a"]

        with pytest.raises(CircularDependencyError):
            topological_sort(reg)


@pytest.mark.unit
class TestInjectDeps:
    """Tests for inject_deps function."""

    def test_simple_injection(self) -> None:
        """Test simple dependency injection."""
        reg = Registry()

        class Dep:
            pass

        class Service:
            pass

        reg.register(Dep, meta=ServiceMeta(name="dep", deps=[]))
        reg.register(Service, meta=ServiceMeta(name="service", deps=[Dep]))

        dep_instance = Dep()
        service_instance = Service()

        reg.get_by_class(Dep).instance = dep_instance

        entry = ServiceEntry(cls=Service, name="service", instance=service_instance, deps=[Dep])

        inject_deps(service_instance, entry, reg)

        assert hasattr(service_instance, "dep")
        assert service_instance.dep is dep_instance

    def test_missing_instance(self) -> None:
        """Test that missing dependency instance raises error."""
        reg = Registry()

        class Dep:
            pass

        class Service:
            pass

        reg.register(Dep, meta=ServiceMeta(name="dep", deps=[]))

        service_instance = Service()

        entry = ServiceEntry(cls=Service, name="service", instance=service_instance, deps=[Dep])

        with pytest.raises(DependencyInjectionError):
            inject_deps(service_instance, entry, reg)
