"""Unit tests for core.module module."""

import pytest

from canary_framework.common.config import CanaryConfig
from canary_framework.core.module import ModuleBase


@pytest.mark.unit
class TestModuleBase:
    """Tests for ModuleBase class."""

    def test_initialization(self) -> None:
        """Test initialization."""
        module = ModuleBase()
        assert module._cf_parent_registry is None
        assert module._cf_registry is None
        assert module._cf_startup_order == []
        assert module._cf_asgi_app is None
        assert module.config is None

    @pytest.mark.asyncio
    async def test_configure_empty_module(self) -> None:
        """Test configure on empty module."""
        module = ModuleBase()
        config = CanaryConfig(host="0.0.0.0")
        await module.configure(config)
        assert module.config == config

    def test_asgi_app_lazy_loaded(self) -> None:
        """Test asgi_app is lazily loaded."""
        module = ModuleBase()
        assert module._cf_asgi_app is None
        app = module.asgi_app
        assert module._cf_asgi_app is not None
        assert app is module._cf_asgi_app

    def test_asgi_app_empty_module_has_no_docs(self) -> None:
        """Test asgi_app on empty module has no docs (docs come from routers)."""
        module = ModuleBase()
        app = module.asgi_app
        routes = app.routes
        paths = [route.path for route in routes]  # type: ignore[attr-defined]
        assert "/openapi.json" not in paths
        assert "/docs" not in paths
        assert "/redoc" not in paths
