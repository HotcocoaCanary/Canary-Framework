"""Integration tests for module registry."""

import pytest

from canary_framework import module, service


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

        app = MyModule()
        await app.configure()  # type: ignore[attr-defined]

        # Check that registry has both services
        assert app._cf_registry is not None  # type: ignore[attr-defined]
        assert app._cf_registry.has(Service1)  # type: ignore[attr-defined]
        assert app._cf_registry.has(Service2)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_service_instances_created(self) -> None:
        """Test that service instances are created."""

        @service()
        class MyService:
            pass

        @module(services=[MyService])
        class MyModule:
            pass

        app = MyModule()
        await app.configure()  # type: ignore[attr-defined]

        # Check that service instance is created
        entry = app._cf_registry.get_by_class(MyService)  # type: ignore[attr-defined]
        assert entry.instance is not None
        assert isinstance(entry.instance, MyService)

    @pytest.mark.asyncio
    async def test_parent_child_module(self) -> None:
        """Test parent and child modules."""

        @service()
        class SharedService:
            def get_value(self) -> str:
                return "shared"

        @service(deps=[SharedService])
        class ChildService:
            pass

        @module(services=[SharedService, ChildService])
        class ChildModule:
            pass

        @module(services=[ChildModule])
        class ParentModule:
            pass

        app = ParentModule()
        await app.configure()  # type: ignore[attr-defined]

        # Check that shared service is available
        assert app.child_module is not None  # type: ignore[attr-defined]
        assert hasattr(app.child_module.child_service, "shared_service")  # type: ignore[attr-defined]
        assert app.child_module.child_service.shared_service.get_value() == "shared"  # type: ignore[attr-defined]
