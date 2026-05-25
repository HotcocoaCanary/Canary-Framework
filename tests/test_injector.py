"""Tests for :mod:`canary_framework.core.engine.injector`."""

from __future__ import annotations

import pytest

from canary_framework.core.decorators.service import service
from canary_framework.core.engine.injector import inject_deps
from canary_framework.core.registry.registry import Registry
from canary_framework.exceptions import DependencyInjectionError


class TestInjectDeps:
    """Unit tests for the dependency injection engine."""

    def test_basic_injection(self) -> None:
        @service("db")
        class DBService:
            connected: bool = True

        @service("user", deps=[DBService])
        class UserService:
            pass

        reg = Registry()
        reg.register(DBService)
        reg.register(UserService)

        user_entry = reg.get_by_name("user")
        inject_deps(user_entry.instance, user_entry, reg)

        assert user_entry.instance.db_service.connected is True  # type: ignore[attr-defined]

    def test_multiple_dependencies(self) -> None:
        @service("db")
        class DBService:
            pass

        @service("cache")
        class CacheService:
            pass

        @service("app", deps=[DBService, CacheService])
        class AppService:
            pass

        reg = Registry()
        for cls in (DBService, CacheService, AppService):
            reg.register(cls)

        app_entry = reg.get_by_name("app")
        inject_deps(app_entry.instance, app_entry, reg)

        assert isinstance(app_entry.instance.db_service, DBService)  # type: ignore[attr-defined]
        assert isinstance(app_entry.instance.cache_service, CacheService)  # type: ignore[attr-defined]

    def test_injection_before_instance_raises(self) -> None:
        @service("db")
        class DBService:
            pass

        @service("user", deps=[DBService])
        class UserService:
            pass

        reg = Registry()
        reg.register(DBService)
        reg.register(UserService)

        # Manually clear the instance to simulate uninitialised state
        user_entry = reg.get_by_name("user")
        dep_entry = reg.get_by_name("db")
        dep_entry.instance = None

        with pytest.raises(DependencyInjectionError, match="instance is None"):
            inject_deps(user_entry.instance, user_entry, reg)

    def test_snake_case_conversion(self) -> None:
        @service("dataset-admin")
        class DataSetAdminService:
            pass

        @service("app", deps=[DataSetAdminService])
        class App:
            pass

        reg = Registry()
        reg.register(DataSetAdminService)
        reg.register(App)

        app_entry = reg.get_by_name("app")
        inject_deps(app_entry.instance, app_entry, reg)

        assert hasattr(app_entry.instance, "data_set_admin_service")
