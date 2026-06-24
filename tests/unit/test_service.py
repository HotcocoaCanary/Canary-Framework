"""Unit tests for core.service module."""

import pytest

from canary_framework.core.service import ServiceBase


@pytest.mark.unit
class TestServiceBase:
    """Tests for ServiceBase class."""

    def test_initialization(self) -> None:
        """Test initialization sets up attributes."""
        service = ServiceBase()
        assert service._cf_parent_registry is None

    @pytest.mark.asyncio
    async def test_init_no_effect(self) -> None:
        """Test that init() runs without errors when no hooks are registered."""

        class MyService(ServiceBase):
            pass

        service = MyService()
        service.init()  # should not raise
