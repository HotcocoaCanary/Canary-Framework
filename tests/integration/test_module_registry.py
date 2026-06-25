"""Integration tests for module registry."""

import pytest

from canary_framework import Canary, module, service


@pytest.mark.integration
class TestModuleRegistry:
    """Integration tests for module registry."""

    @pytest.mark.asyncio
    async def test_registry_has_services(self) -> None:
        """Test that registry contains all services."""

        @service()
        class Service1:
            pass

        @service()
        class Service2:
            pass

        @module(services=[Service1, Service2])
        class MyModule:
            pass

        app = Canary(MyModule())

        # Check that registry has both services
        assert app._registry is not None
        assert app._registry.has(Service1)
        assert app._registry.has(Service2)

    @pytest.mark.asyncio
    async def test_service_instances_created(self) -> None:
        """Test that service instances are created."""

        @service()
        class MyService:
            pass

        @module(services=[MyService])
        class MyModule:
            pass

        app = Canary(MyModule())

        # Check that service instance is created
        entry = app._registry.get_by_class(MyService)
        assert entry.instance is not None
        assert isinstance(entry.instance, MyService)

    @pytest.mark.asyncio
    async def test_parent_child_module(self) -> None:
        """Test parent and child modules."""

        @service()
        class SharedService:
            def get_value(self) -> str:
                return "shared"

        @service()
        class ChildService:
            shared_service: SharedService

        @module(services=[SharedService, ChildService])
        class ChildModule:
            pass

        @module(services=[ChildModule])
        class ParentModule:
            pass

        app = Canary(ParentModule())

        # Check that shared service is available
        assert app.ChildModule is not None  # type: ignore[attr-defined]
        assert hasattr(app.ChildService, "shared_service")  # type: ignore[attr-defined]
        assert app.ChildService.shared_service.get_value() == "shared"  # type: ignore[attr-defined]
