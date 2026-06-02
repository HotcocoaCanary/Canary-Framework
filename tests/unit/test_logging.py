"""Unit tests for logging functionality."""

from __future__ import annotations

import logging
from typing import Any, cast
from unittest.mock import patch

from canary_framework.core import ModuleBase, RouterBase, ServiceBase
from canary_framework.decorators import get, module, router, service
from canary_framework.engine.logging import ensure_logging


class TestLogging:
    async def test_service_lifecycle_logging(self) -> None:
        """Test that ServiceBase logs lifecycle events."""

        @service()
        class TestService:
            pass

        with patch("canary_framework.core.service._log") as mock_log:
            service_inst = cast(ServiceBase, TestService())
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

        @module()
        class TestModule:
            pass

        with patch("canary_framework.core.module._log") as mock_log:
            module_inst = cast(ModuleBase, TestModule())
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

            @service()
            class RegistryTestService:
                pass

            registry.register(RegistryTestService)

            mock_log.debug.assert_any_call(
                "Registered service/module: %s -> %s",
                "RegistryTestService",
                "RegistryTestServiceService",
            )

    async def test_router_logging(self) -> None:
        """Test that RouterBase logs route collection."""

        @router()
        class TestLogRouter:
            @get("/test")
            async def test_handler(self, request):  # type: ignore[no-untyped-def]
                return {"message": "test"}

        with patch("canary_framework.core.router._log") as mock_log:
            router_inst = cast(RouterBase, TestLogRouter())
            _ = router_inst.asgi_app

            mock_log.debug.assert_any_call(
                "Collected %d route(s) for router: %s", 1, "TestLogRouter"
            )
            mock_log.debug.assert_any_call("  Route: %s %s", {"GET", "HEAD"}, "/test")

    async def test_dependency_injection_logging(self) -> None:
        """Test that dependency injection logs are generated."""

        @service()
        class DepService:
            pass

        @service(deps=[DepService])
        class MainService:
            pass

        with patch("canary_framework.engine.injector._log") as mock_log:

            @module(services=[DepService, MainService])
            class DiTestModule:
                pass

            module_inst = cast(ModuleBase, DiTestModule())
            await module_inst.configure()

            mock_log.debug.assert_any_call("Injecting dependencies into: %s", "MainServiceService")
            mock_log.debug.assert_any_call("  %s  →  self.%s", "DepService", "dep_service")

    async def test_ensure_logging_adds_handler(self) -> None:
        """Test that ensure_logging adds a StreamHandler to cf logger."""
        import logging

        import canary_framework.engine.logging as log_mod

        original_initialized = log_mod._logging_initialized
        log_mod._logging_initialized = False

        cf_logger = logging.getLogger("cf")
        cf_logger.handlers.clear()
        cf_logger.propagate = True

        root = logging.getLogger()
        original_root_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            ensure_logging("DEBUG")

            assert len(cf_logger.handlers) == 1
            handler = cf_logger.handlers[0]
            assert isinstance(handler, logging.StreamHandler)
            assert cf_logger.level == logging.DEBUG
        finally:
            _reset_logging_state(
                cf_logger, root, original_root_handlers, original_initialized, log_mod
            )

    async def test_ensure_logging_idempotent(self) -> None:
        """Test that ensure_logging only adds handler once."""
        import logging

        import canary_framework.engine.logging as log_mod

        original_initialized = log_mod._logging_initialized
        log_mod._logging_initialized = False

        cf_logger = logging.getLogger("cf")
        cf_logger.handlers.clear()
        cf_logger.propagate = True

        root = logging.getLogger()
        original_root_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            ensure_logging("INFO")
            first_count = len(cf_logger.handlers)
            ensure_logging("DEBUG")
            second_count = len(cf_logger.handlers)

            assert first_count == 1
            assert second_count == 1
        finally:
            _reset_logging_state(
                cf_logger, root, original_root_handlers, original_initialized, log_mod
            )

    async def test_ensure_logging_skips_if_cf_has_handler(self) -> None:
        """Test that ensure_logging skips if cf logger already has a handler."""
        import logging

        import canary_framework.engine.logging as log_mod

        original_initialized = log_mod._logging_initialized
        log_mod._logging_initialized = False

        cf_logger = logging.getLogger("cf")
        existing = logging.StreamHandler()
        cf_logger.handlers.clear()
        cf_logger.addHandler(existing)
        cf_logger.propagate = True

        try:
            ensure_logging("INFO")

            assert cf_logger.handlers == [existing]
            assert log_mod._logging_initialized is True
        finally:
            _reset_logging_state(cf_logger, logging.getLogger(), [], original_initialized, log_mod)

    async def test_ensure_logging_skips_if_root_has_handler(self) -> None:
        """Test that ensure_logging skips if root logger already has a handler."""
        import logging

        import canary_framework.engine.logging as log_mod

        original_initialized = log_mod._logging_initialized
        log_mod._logging_initialized = False

        cf_logger = logging.getLogger("cf")
        cf_logger.handlers.clear()
        cf_logger.propagate = True

        root = logging.getLogger()
        root.handlers.clear()
        existing = logging.StreamHandler()
        root.addHandler(existing)

        try:
            ensure_logging("INFO")

            assert len(cf_logger.handlers) == 0
            assert log_mod._logging_initialized is True
        finally:
            _reset_logging_state(cf_logger, root, [], original_initialized, log_mod)

    async def test_module_configure_calls_ensure_logging(self) -> None:
        """Test that ModuleBase.configure() triggers ensure_logging."""
        import logging

        import canary_framework.engine.logging as log_mod

        original_initialized = log_mod._logging_initialized
        log_mod._logging_initialized = False

        cf_logger = logging.getLogger("cf")
        cf_logger.handlers.clear()

        root = logging.getLogger()
        original_root_handlers = root.handlers[:]
        root.handlers.clear()

        try:

            @module()
            class TestLogModule:
                pass

            module_inst = cast(ModuleBase, TestLogModule())
            await module_inst.configure()

            assert log_mod._logging_initialized is True
        finally:
            _reset_logging_state(
                cf_logger, root, original_root_handlers, original_initialized, log_mod
            )


def _reset_logging_state(
    cf_logger: logging.Logger,
    root: logging.Logger,
    original_root_handlers: list[logging.Handler],
    original_initialized: bool,
    log_mod: Any,
) -> None:
    cf_logger.handlers.clear()
    cf_logger.propagate = True
    root.handlers.clear()
    for h in original_root_handlers:
        root.addHandler(h)
    log_mod._logging_initialized = original_initialized
