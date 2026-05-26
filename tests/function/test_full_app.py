"""Functional (end-to-end) tests for Canary Framework.

Tests the complete application lifecycle from the user's perspective:
@config → @service/@module → Canary.init/start/stop
"""

from __future__ import annotations

import pytest


@pytest.mark.functional
class TestFullApplicationLifecycle:
    """Verify the complete application flow from declaration to shutdown."""

    async def test_full_init_start_stop_with_config_and_deps(self) -> None:
        from canary_framework import (
            Canary,
            config,
            module,
            on_end,
            on_init,
            on_start,
            service,
        )

        @config
        class AppConfig:
            app_name: str = "myapp"
            debug: bool = False

        @service("logger")
        class LoggerService:
            messages: list[str]

            def __init__(self) -> None:
                self.messages = []

            def log(self, msg: str) -> None:
                self.messages.append(msg)

        @service("db", config=AppConfig)
        class DBService:
            connected: bool
            app_config: AppConfig

            def __init__(self) -> None:
                self.connected = False

            @on_init
            def init(self) -> None:
                self.name = self.app_config.app_name
                self.connected = True

            @on_end
            def stop(self) -> None:
                self.connected = False

        @service("worker", deps=[LoggerService, DBService])
        class WorkerService:
            logger_service: LoggerService
            db_service: DBService
            app_config: AppConfig

            @on_init
            def init(self) -> None:
                self.logger_service.log(f"worker init: {self.app_config.app_name}")

            @on_start
            def start(self) -> None:
                self.logger_service.log("worker started")

            @on_end
            def stop(self) -> None:
                self.logger_service.log("worker stopped")

        @module("app", config=AppConfig, services=[LoggerService, DBService, WorkerService])
        class AppModule:
            pass

        app = Canary(AppModule)
        await app.init()
        await app.start()
        await app.stop()

        # Verify lifecycle executed correctly
        db: DBService = app.registry.get_instance(DBService)  # type: ignore[assignment]
        assert db.connected is False
        assert db.name == "myapp"

        logger: LoggerService = app.registry.get_instance(LoggerService)  # type: ignore[assignment]
        assert "worker init: myapp" in logger.messages
        assert "worker started" in logger.messages
        assert "worker stopped" in logger.messages

    async def test_nested_modules_with_config_inheritance(self) -> None:
        from canary_framework import (
            Canary,
            config,
            module,
            on_init,
            service,
        )

        @config
        class RootCfg:
            env: str = "production"
            secret: str = "s3cret"

        @service("inner-svc")
        class InnerService:
            cfg_env: str = ""
            root_cfg: RootCfg

            @on_init
            def init(self) -> None:
                self.cfg_env = self.root_cfg.env

        @module("inner", services=[InnerService])
        class InnerModule:
            pass

        @module("root", config=RootCfg, services=[InnerModule])
        class RootModule:
            pass

        app = Canary(RootModule)
        await app.init()

        inner: InnerService = app.registry.get_instance(InnerService)  # type: ignore[assignment]
        assert inner.cfg_env == "production"

    async def test_multiple_modules_cross_dependency(self) -> None:
        from canary_framework import (
            Canary,
            module,
            on_init,
            service,
        )

        @service("calc")
        class CalcService:
            def add(self, a: int, b: int) -> int:
                return a + b

        @service("reporter", deps=[CalcService])
        class ReporterService:
            calc_service: CalcService
            result: int = 0

            @on_init
            def init(self) -> None:
                self.result = self.calc_service.add(3, 4)

        @module("math", services=[CalcService])
        class MathModule:
            pass

        @module("report", services=[ReporterService])
        class ReportModule:
            pass

        @module("root", services=[MathModule, ReportModule])
        class RootModule:
            pass

        app = Canary(RootModule)
        await app.init()

        reporter: ReporterService = app.registry.get_instance(ReporterService)  # type: ignore[assignment]
        assert reporter.result == 7


@pytest.mark.functional
class TestErrorScenarios:
    """Verify framework handles error scenarios gracefully."""

    async def test_init_hook_raises_wraps_in_lifecycle_error(self) -> None:
        from canary_framework import Canary, service
        from canary_framework.common.exceptions import LifecycleHookError
        from canary_framework.core.decorators.lifecycle import on_init

        @service("broken")
        class BrokenService:
            @on_init
            def init(self) -> None:
                raise RuntimeError("init failed")

        app = Canary(BrokenService)
        with pytest.raises(LifecycleHookError, match="init failed"):
            await app.init()

    async def test_circular_dependency_is_detected(self) -> None:
        from canary_framework.common.exceptions import CircularDependencyError
        from canary_framework.core.algorithms.sorter import topological_sort
        from canary_framework.core.container.registry import Registry
        from canary_framework.core.decorators.service import service

        @service("a")
        class A:
            pass

        @service("b")
        class B:
            pass

        reg = Registry()
        reg.register(A)
        reg.register(B)
        a_entry = reg.get_by_class(A)
        a_entry.dep_names = ["b"]
        b_entry = reg.get_by_class(B)
        b_entry.dep_names = ["a"]

        with pytest.raises(CircularDependencyError):
            topological_sort(reg)

    async def test_duplicate_service_name_is_rejected(self) -> None:
        from canary_framework.core.container.registry import Registry
        from canary_framework.core.decorators.service import service

        @service("dup")
        class SvcA:
            pass

        @service("dup")
        class SvcB:
            pass

        reg = Registry()
        reg.register(SvcA)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(SvcB)
