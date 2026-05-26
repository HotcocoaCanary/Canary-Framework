"""Tests for config and service resolution via dependency injection."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from canary_framework.core.conductor.canary import Canary
from canary_framework.core.decorators.lifecycle import on_init
from canary_framework.core.decorators.module import module
from canary_framework.core.decorators.service import service


@pytest.mark.integration
class TestDIConfigInjection:
    """Verify typed config access via dependency injection."""

    async def test_get_config_returns_typed_config(self) -> None:
        class MyCfg(BaseModel):
            key: str = "val"

        class AppConfig(BaseModel):
            s: MyCfg = MyCfg()

        @service("s")
        class Svc:
            @on_init
            def init(self) -> None:
                pass

        app = Canary(Svc)
        await app.config(config=AppConfig())
        await app.init()

        inst: Svc = app.registry.get_instance(Svc)  # type: ignore[assignment]
        assert inst.key == "val"  # type: ignore[attr-defined]

    async def test_config_chain_upward(self) -> None:
        class SvcCfg(BaseModel):
            env: str = "prod"

        class AppConfig(BaseModel):
            root: SvcCfg = SvcCfg()
            child: SvcCfg = SvcCfg()

        @service("child")
        class ChildSvc:
            @on_init
            def init(self) -> None:
                pass

        @module("root", services=[ChildSvc])
        class Root:
            pass

        app = Canary(Root)
        await app.config(config=AppConfig())
        await app.init()

        inst: ChildSvc = app.registry.get_instance(ChildSvc)  # type: ignore[assignment]
        assert inst.env == "prod"  # type: ignore[attr-defined]

    async def test_no_config_raises(self) -> None:
        @service("orphan")
        class Orphan:
            pass

        app = Canary(Orphan)
        await app.config()

        inst: Orphan = app.registry.get_instance(Orphan)  # type: ignore[assignment]
        with pytest.raises(AttributeError):
            _ = inst.unbound_cfg  # type: ignore[attr-defined]


@pytest.mark.integration
class TestDIServiceInjection:
    """Verify typed service resolution via dependency injection."""

    async def test_get_service_finds_in_module_tree(self) -> None:
        @service("db")
        class DBService:
            pass

        @service("user", deps=[DBService])
        class UserService:
            db_service: DBService

            @on_init
            def init(self) -> None:
                pass

        @module("app", services=[DBService, UserService])
        class App:
            pass

        app = Canary(App)
        await app.config()
        await app.init()

        inst: UserService = app.registry.get_instance(UserService)  # type: ignore[assignment]
        assert isinstance(inst.db_service, DBService)

    async def test_get_service_not_found_raises(self) -> None:
        class Unknown:
            pass

        @service("orphan", deps=[Unknown])
        class Orphan:
            pass

        app = Canary(Orphan)
        with pytest.raises(TypeError, match="not decorated"):
            await app.config()

    async def test_get_service_across_module_boundaries(self) -> None:
        @service("a-svc")
        class ASvc:
            pass

        @service("b-svc")
        class BSvc:
            pass

        @module("sub-a", services=[ASvc])
        class SubA:
            pass

        @module("sub-b", services=[BSvc])
        class SubB:
            pass

        @module("root", services=[SubA, SubB])
        class Root:
            pass

        app = Canary(Root)
        await app.config()

        a_inst: ASvc = app.registry.get_instance(ASvc)  # type: ignore[assignment]
        with pytest.raises(AttributeError):
            _ = a_inst.bsvc  # type: ignore[attr-defined]

    async def test_get_service_returns_typed_instance(self) -> None:
        @service("mysvc")
        class MySvc:
            pass

        @service("consumer", deps=[MySvc])
        class Consumer:
            my_svc: MySvc

            @on_init
            def init(self) -> None:
                pass

        app = Canary(Consumer)
        await app.config()
        await app.init()

        inst: Consumer = app.registry.get_instance(Consumer)  # type: ignore[assignment]
        assert isinstance(inst.my_svc, MySvc)
