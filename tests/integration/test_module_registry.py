"""Integration tests for module registry."""

import pytest

from canary_framework import module, service
from canary_framework.core.module import ModuleBase
from canary_framework.core.service import ServiceBase


@pytest.mark.integration
class TestModuleRegistry:
    """Integration tests for module registry."""

    @pytest.mark.asyncio
    async def test_registry_has_services(self) -> None:
        """Test that registry contains all services."""

        @service()
        class Service1(ServiceBase):
            pass

        @service()
        class Service2(ServiceBase):
            pass

        @module(services=[Service1, Service2])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        app.init()

        # Check that registry has both services
        assert app._cf_registry is not None
        assert app._cf_registry.has(Service1)
        assert app._cf_registry.has(Service2)

    @pytest.mark.asyncio
    async def test_service_instances_created(self) -> None:
        """Test that service instances are created."""

        @service()
        class MyService(ServiceBase):
            pass

        @module(services=[MyService])
        class MyModule(ModuleBase):
            pass

        app = MyModule()
        app.init()

        # Check that service instance is created
        entry = app._cf_registry.get_by_class(MyService)  # type: ignore[union-attr]
        assert entry.instance is not None
        assert isinstance(entry.instance, MyService)

    @pytest.mark.asyncio
    async def test_parent_child_module(self) -> None:
        """Test parent and child modules."""

        @service()
        class SharedService(ServiceBase):
            def get_value(self) -> str:
                return "shared"

        @service()
        class ChildService(ServiceBase):
            shared_service: SharedService

        @module(services=[SharedService, ChildService])
        class ChildModule(ModuleBase):
            pass

        @module(services=[ChildModule])
        class ParentModule(ModuleBase):
            pass

        app = ParentModule()
        app.init()

        # Check that shared service is available
        assert app.ChildModule is not None  # type: ignore[attr-defined]
        assert hasattr(app.ChildModule.ChildService, "shared_service")  # type: ignore[attr-defined]
        assert app.ChildModule.ChildService.shared_service.get_value() == "shared"  # type: ignore[attr-defined]
