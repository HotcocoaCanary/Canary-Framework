"""Tests for :mod:`canary_framework.core.conductor.context`."""

from __future__ import annotations

import pytest

from canary_framework.common.exceptions import ConfigurationError, ServiceNotFoundError
from canary_framework.core.conductor.canary import Canary
from canary_framework.core.decorators.config import config
from canary_framework.core.decorators.module import module
from canary_framework.core.decorators.service import service


class TestContextGetConfig:
    """Verify typed config access via get_config()."""

    async def test_get_config_returns_typed_config(self) -> None:
        @config
        class MyCfg:
            key: str = "val"

        @service("s", config=MyCfg)
        class Svc:
            pass

        app = Canary(Svc)
        await app.init()

        entry = app.registry.get_by_class(Svc)
        ctx = entry.context
        assert ctx is not None
        cfg = ctx.get_config(MyCfg)
        assert cfg.key == "val"

    async def test_config_chain_upward(self) -> None:
        @config
        class RootCfg:
            env: str = "prod"

        @service("child")
        class ChildSvc:
            pass

        @module("root", config=RootCfg, services=[ChildSvc])
        class Root:
            pass

        app = Canary(Root)
        await app.init()

        child_entry = app.registry.get_by_name("child")
        ctx = child_entry.context
        assert ctx is not None
        cfg = ctx.get_config(RootCfg)
        assert cfg.env == "prod"

    async def test_no_config_raises(self) -> None:
        @service("orphan")
        class Orphan:
            pass

        app = Canary(Orphan)
        await app.init()

        entry = app.registry.get_by_class(Orphan)
        ctx = entry.context
        assert ctx is not None
        with pytest.raises(ConfigurationError, match="No config instance"):
            ctx.get_config(object)


class TestContextGetService:
    """Verify typed service resolution via get_service()."""

    async def test_get_service_finds_in_module_tree(self) -> None:
        @service("db")
        class DBService:
            pass

        @service("user", deps=[DBService])
        class UserService:
            pass

        @module("app", services=[DBService, UserService])
        class App:
            pass

        app = Canary(App)
        await app.init()

        user_entry = app.registry.get_by_name("user")
        ctx = user_entry.context
        assert ctx is not None
        db = ctx.get_service(DBService)
        assert isinstance(db, DBService)

    async def test_get_service_not_found_raises(self) -> None:
        @service("orphan")
        class Orphan:
            pass

        class Unknown:
            pass

        app = Canary(Orphan)
        await app.init()

        entry = app.registry.get_by_class(Orphan)
        ctx = entry.context
        assert ctx is not None
        with pytest.raises(ServiceNotFoundError, match="not found"):
            ctx.get_service(Unknown)

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
        await app.init()

        a_entry = app.registry.get_by_name("a-svc")
        ctx = a_entry.context
        assert ctx is not None
        with pytest.raises(ServiceNotFoundError):
            ctx.get_service(BSvc)

    async def test_get_service_returns_typed_instance(self) -> None:
        @service("mysvc")
        class MySvc:
            pass

        app = Canary(MySvc)
        await app.init()

        entry = app.registry.get_by_class(MySvc)
        ctx = entry.context
        assert ctx is not None
        inst = ctx.get_service(MySvc)
        assert isinstance(inst, MySvc)
