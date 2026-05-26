"""Tests for :mod:`canary_framework.core.decorators.service`.

Covers:
    - get_service_meta fallback for non-service classes
"""

from __future__ import annotations

import pytest

from canary_framework.common._types import ServiceMeta
from canary_framework.core.decorators.service import get_service_meta, is_cf_service, service


@pytest.mark.unit
class TestGetServiceMeta:
    """Verify get_service_meta() introspection."""

    def test_returns_service_meta_for_service(self) -> None:
        @service("test-svc")
        class Svc:
            pass

        meta = get_service_meta(Svc)
        assert isinstance(meta, ServiceMeta)
        assert meta.name == "test-svc"

    def test_returns_default_for_non_service(self) -> None:
        class Plain:
            pass

        meta = get_service_meta(Plain)
        assert isinstance(meta, ServiceMeta)
        assert meta.name == ""


@pytest.mark.unit
class TestIsCfService:
    """Verify is_cf_service() detection."""

    def test_true_for_service(self) -> None:
        @service("svc")
        class Svc:
            pass

        assert is_cf_service(Svc) is True

    def test_false_for_plain_class(self) -> None:
        class Plain:
            pass

        assert is_cf_service(Plain) is False
