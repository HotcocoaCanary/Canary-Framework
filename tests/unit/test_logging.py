"""Unit tests for logging functionality."""

from __future__ import annotations

from unittest.mock import patch

from canary_framework.decorators import get, module, router, service


class TestLogging:
    async def test_service_lifecycle_logging(self) -> None:
        """Test that ServiceBase logs lifecycle events."""

        @service(name="test_service")
        class TestService:
            pass

        with patch("canary_framework.core.service._log") as mock_log:
            service_inst = TestService()
            await service_inst.configure()
            await service_inst.init()
            await service_inst.startup()
            await service_inst.shutdown()

            mock_log.debug.assert_any_call("Configuring service: %s", "TestService")
            mock_log.debug.assert_any_call("Initializing service: %s", "TestService")
            mock_log.debug.assert_any_call("Starting service: %s", "TestService")
            mock_log.debug.assert_any_call("Shutting down service: %s", "TestService")

    async def test_module_lifecycle_logging(self) -> None:
        """Test that ModuleBase logs lifecycle events at INFO level."""

        @module(name="test_module")
        class TestModule:
            pass

        with patch("canary_framework.core.module._log") as mock_log:
            module_inst = TestModule()
            await module_inst.configure()
            await module_inst.init()
            await module_inst.startup()
            await module_inst.shutdown()

            mock_log.info.assert_any_call("Configuring module: %s", "TestModule")
            mock_log.info.assert_any_call("Initializing module: %s", "TestModule")
            mock_log.info.assert_any_call("Starting module: %s", "TestModule")
            mock_log.info.assert_any_call("Shutting down module: %s", "TestModule")

    async def test_registry_logging(self) -> None:
        """Test that Registry logs service registration."""

        from canary_framework.engine.registry import Registry

        with patch("canary_framework.engine.registry._log") as mock_log:
            registry = Registry()

            @service(name="registry_test_service")
            class RegistryTestService:
                pass

            registry.register(RegistryTestService)

            mock_log.debug.assert_any_call(
                "Registered service/module: %s -> %s",
                "RegistryTestService",
                "registry_test_service",
            )

    async def test_router_logging(self) -> None:
        """Test that RouterBase logs route collection."""

        @router(name="test_log_router")
        class TestLogRouter:
            @get("/test")
            async def test_handler(self, request):  # type: ignore[no-untyped-def]
                return {"message": "test"}

        with patch("canary_framework.core.router._log") as mock_log:
            router_inst = TestLogRouter()
            _ = router_inst.asgi_app

            mock_log.debug.assert_any_call(
                "Collected %d route(s) for router: %s", 1, "TestLogRouter"
            )
            mock_log.debug.assert_any_call("  Route: %s %s", {"GET", "HEAD"}, "/test")

    async def test_dependency_injection_logging(self) -> None:
        """Test that dependency injection logs are generated."""

        @service(name="dep_service")
        class DepService:
            pass

        @service(name="main_service", deps=[DepService])
        class MainService:
            pass

        with patch("canary_framework.engine.injector._log") as mock_log:

            @module(name="di_test_module", services=[DepService, MainService])
            class DiTestModule:
                pass

            module_inst = DiTestModule()
            await module_inst.configure()

            mock_log.debug.assert_any_call("Injecting dependencies into: %s", "main_service")
            mock_log.debug.assert_any_call("  %s  →  self.%s", "DepService", "dep_service")
