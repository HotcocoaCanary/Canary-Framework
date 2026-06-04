"""Unit tests for decorators.service module."""

import pytest

from canary_framework.common import get_service_meta, is_cf_service
from canary_framework.core.service import ServiceBase
from canary_framework.decorators.service import service


@pytest.mark.unit
class TestServiceDecorator:
    """Tests for @service decorator."""

    def test_service_decorator_marks_class(self) -> None:
        """Test @service marks class as service."""

        @service()
        class MyService(ServiceBase):
            pass

        assert is_cf_service(MyService)

    def test_service_decorator_inherits_service_base(self) -> None:
        """Test @service makes class inherit from ServiceBase."""

        @service()
        class MyService(ServiceBase):
            pass

        assert issubclass(MyService, ServiceBase)

    def test_service_decorator_sets_meta(self) -> None:
        """Test @service sets metadata."""

        @service()
        class MyService(ServiceBase):
            pass

        meta = get_service_meta(MyService)
        assert meta.name == "MyServiceService"
