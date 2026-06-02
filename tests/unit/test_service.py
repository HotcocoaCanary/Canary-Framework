"""Unit tests for @service decorator."""

from __future__ import annotations

from canary_framework.common import ServiceMeta, get_service_meta, is_cf_service
from canary_framework.core import ServiceBase
from canary_framework.decorators import (
    after_config,
    after_init,
    before_shutdown,
    before_startup,
    service,
)


class TestServiceDecorator:
    def test_service_injects_base_class(self) -> None:
        @service()
        class MyService:
            pass

        assert issubclass(MyService, ServiceBase)

    def test_is_cf_service_returns_true(self) -> None:
        @service()
        class Svc:
            pass

        assert is_cf_service(Svc) is True

    def test_is_cf_service_returns_false(self) -> None:
        class Plain:
            pass

        assert is_cf_service(Plain) is False

    def test_get_service_meta(self) -> None:
        @service()
        class DBService:
            pass

        meta = get_service_meta(DBService)
        assert isinstance(meta, ServiceMeta)
        assert meta.name == "DBServiceService"
        assert meta.deps == []

    def test_service_with_deps(self) -> None:
        @service()
        class A:
            pass

        @service(deps=[A])
        class B:
            pass

        meta = get_service_meta(B)
        assert meta.deps == [A]


class TestServiceLifecycle:
    async def test_after_config(self) -> None:
        calls: list[str] = []

        @service()
        class Svc:
            @after_config
            def hook(self) -> None:
                calls.append("after_config")

        inst = Svc()
        await inst.configure()  # type: ignore[attr-defined]
        assert "after_config" in calls

    async def test_after_init(self) -> None:
        calls: list[str] = []

        @service()
        class Svc:
            @after_init
            def hook(self) -> None:
                calls.append("after_init")

        inst = Svc()
        await inst.configure()  # type: ignore[attr-defined]
        await inst.init()  # type: ignore[attr-defined]
        assert "after_init" in calls

    async def test_before_startup(self) -> None:
        calls: list[str] = []

        @service()
        class Svc:
            @before_startup
            def hook(self) -> None:
                calls.append("before_startup")

        inst = Svc()
        await inst.configure()  # type: ignore[attr-defined]
        await inst.init()  # type: ignore[attr-defined]
        await inst.startup()  # type: ignore[attr-defined]
        assert "before_startup" in calls

    async def test_before_shutdown(self) -> None:
        calls: list[str] = []

        @service()
        class Svc:
            @before_shutdown
            def hook(self) -> None:
                calls.append("before_shutdown")

        inst = Svc()
        await inst.configure()  # type: ignore[attr-defined]
        await inst.init()  # type: ignore[attr-defined]
        await inst.startup()  # type: ignore[attr-defined]
        await inst.shutdown()  # type: ignore[attr-defined]
        assert "before_shutdown" in calls

    async def test_config_loaded(self) -> None:
        class AppConfig:
            name: str = "canary"

        captured: dict[str, str] = {}

        @service()
        class Svc:
            @after_config
            def hook(self) -> None:
                captured["name"] = self.config.name  # type: ignore[attr-defined]

        inst = Svc()
        await inst.configure(AppConfig())  # type: ignore[attr-defined]
        assert captured.get("name") == "canary"
