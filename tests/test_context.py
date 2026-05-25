"""Tests for :mod:`canary_framework.core.engine.context`."""

from __future__ import annotations

import pytest

from canary_framework.core.decorators.config import config
from canary_framework.core.decorators.module import module
from canary_framework.core.decorators.service import service
from canary_framework.core.engine.canary import Canary
from canary_framework.exceptions import ConfigurationError, ServiceNotFoundError


class TestContextConfigAs:
    """Verify typed config access via config_as()."""

    async def test_config_as_returns_typed_config(self) -> None:
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
        cfg = ctx.config_as(MyCfg)
        assert cfg.key == "val"

    async def test_config_chain_upward(self) -> None:
        """A child service inherits config from parent module."""

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
        cfg = ctx.config_as(RootCfg)
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
            ctx.config_as(object)


class TestContextResolve:
    """Verify dependency resolution via resolve()."""

    async def test_resolve_finds_service_in_module_tree(self) -> None:
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
        db = ctx.resolve(DBService)
        assert isinstance(db, DBService)

    async def test_resolve_not_found_raises(self) -> None:
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
            ctx.resolve(Unknown)

    async def test_resolve_across_module_boundaries(self) -> None:
        """Sibling modules should NOT resolve each other's services
        via ctx.resolve (only parent chain is traversed)."""

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

        # BSvc is in SubB, ASvc is in SubA — resolve from ASvc's ctx
        # should NOT find BSvc (not in parent chain)
        a_entry = app.registry.get_by_name("a-svc")
        ctx = a_entry.context
        assert ctx is not None
        with pytest.raises(ServiceNotFoundError):
            ctx.resolve(BSvc)


class TestContextServiceAs:
    """Verify typed service access via service_as()."""

    async def test_service_as_returns_typed_instance(self) -> None:
        @service("mysvc")
        class MySvc:
            pass

        app = Canary(MySvc)
        await app.init()

        entry = app.registry.get_by_class(MySvc)
        ctx = entry.context
        assert ctx is not None
        inst = ctx.service_as(MySvc)
        assert isinstance(inst, MySvc)


class TestContextPropertyRetained:
    """Verify backward-compatible property access still works."""

    async def test_config_property_returns_instance(self) -> None:
        @config
        class Cfg:
            x: int = 42

        @service("s", config=Cfg)
        class Svc:
            pass

        app = Canary(Svc)
        await app.init()

        entry = app.registry.get_by_class(Svc)
        ctx = entry.context
        assert ctx is not None
        cfg_obj = ctx.config()
        assert cfg_obj is not None

    async def test_service_property_returns_instance(self) -> None:
        @service("mysvc")
        class MySvc:
            pass

        app = Canary(MySvc)
        await app.init()

        entry = app.registry.get_by_class(MySvc)
        ctx = entry.context
        assert ctx is not None
        inst = ctx.service()
        assert isinstance(inst, MySvc)
