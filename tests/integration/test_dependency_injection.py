"""Integration tests for dependency injection."""

import pytest

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.service import ServiceBase


@pytest.mark.integration
class TestDependencyInjection:
    """Integration tests for dependency injection."""

    @pytest.mark.asyncio
    async def test_simple_dependency_injection(self) -> None:
        """Test simple dependency injection."""

        @service()
        class Dependency(ServiceBase):
            def get_value(self) -> str:
                return "dependency value"

        @service()
        class MyService(ServiceBase):
            dependency: Dependency

        @module(services=[MyService])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        await app.init()

        # Check that dependency is injected
        assert hasattr(app.MyService, "dependency")  # type: ignore[attr-defined]
        assert app.MyService.dependency.get_value() == "dependency value"  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_multiple_dependencies(self) -> None:
        """Test multiple dependencies."""

        @service()
        class Dep1(ServiceBase):
            def get_value(self) -> str:
                return "dep1"

        @service()
        class Dep2(ServiceBase):
            def get_value(self) -> str:
                return "dep2"

        @service()
        class MyService(ServiceBase):
            dep1: Dep1
            dep2: Dep2

        @module(services=[MyService])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        await app.init()

        assert hasattr(app.MyService, "dep1")  # type: ignore[attr-defined]
        assert hasattr(app.MyService, "dep2")  # type: ignore[attr-defined]
        assert app.MyService.dep1.get_value() == "dep1"  # type: ignore[attr-defined]
        assert app.MyService.dep2.get_value() == "dep2"  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_nested_dependencies(self) -> None:
        """Test nested dependencies."""

        @service()
        class DeepDep(ServiceBase):
            def get_value(self) -> str:
                return "deep"

        @service()
        class MiddleDep(ServiceBase):
            deep_dep: DeepDep

        @service()
        class MyService(ServiceBase):
            middle_dep: MiddleDep

        @module(services=[MyService])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        await app.init()

        assert hasattr(app.MyService, "middle_dep")  # type: ignore[attr-defined]
        assert hasattr(app.MyService.middle_dep, "deep_dep")  # type: ignore[attr-defined]
        assert app.MyService.middle_dep.deep_dep.get_value() == "deep"  # type: ignore[attr-defined]
