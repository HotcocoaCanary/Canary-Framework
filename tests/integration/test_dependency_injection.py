"""Integration tests for dependency injection."""

import pytest

from canary_framework import module, service


@pytest.mark.integration
class TestDependencyInjection:
    """Integration tests for dependency injection."""

    @pytest.mark.asyncio
    async def test_simple_dependency_injection(self) -> None:
        """Test simple dependency injection."""

        @service()
        class Dependency:
            def get_value(self) -> str:
                return "dependency value"

        @service(deps=[Dependency])
        class MyService:
            pass

        @module(services=[MyService])
        class MyModule:
            pass

        app = MyModule()
        await app.configure()  # type: ignore[attr-defined]

        # Check that dependency is injected
        assert hasattr(app.my_service, "dependency")  # type: ignore[attr-defined]
        assert app.my_service.dependency.get_value() == "dependency value"  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_multiple_dependencies(self) -> None:
        """Test multiple dependencies."""

        @service()
        class Dep1:
            def get_value(self) -> str:
                return "dep1"

        @service()
        class Dep2:
            def get_value(self) -> str:
                return "dep2"

        @service(deps=[Dep1, Dep2])
        class MyService:
            pass

        @module(services=[MyService])
        class MyModule:
            pass

        app = MyModule()
        await app.configure()  # type: ignore[attr-defined]

        assert hasattr(app.my_service, "dep1")  # type: ignore[attr-defined]
        assert hasattr(app.my_service, "dep2")  # type: ignore[attr-defined]
        assert app.my_service.dep1.get_value() == "dep1"  # type: ignore[attr-defined]
        assert app.my_service.dep2.get_value() == "dep2"  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_nested_dependencies(self) -> None:
        """Test nested dependencies."""

        @service()
        class DeepDep:
            def get_value(self) -> str:
                return "deep"

        @service(deps=[DeepDep])
        class MiddleDep:
            pass

        @service(deps=[MiddleDep])
        class MyService:
            pass

        @module(services=[MyService])
        class MyModule:
            pass

        app = MyModule()
        await app.configure()  # type: ignore[attr-defined]

        assert hasattr(app.my_service, "middle_dep")  # type: ignore[attr-defined]
        assert hasattr(app.my_service.middle_dep, "deep_dep")  # type: ignore[attr-defined]
        assert app.my_service.middle_dep.deep_dep.get_value() == "deep"  # type: ignore[attr-defined]
