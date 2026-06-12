"""Unit tests for common.markers module."""

import pytest

from canary_framework.common import (
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ModuleMeta,
    ServiceMeta,
    get_module_meta,
    get_service_meta,
    is_cf_module,
    is_cf_service,
)


@pytest.mark.unit
class TestMarkerChecks:
    """Tests for marker checking functions."""

    def test_is_cf_service_positive(self) -> None:
        """Test is_cf_service returns True for marked classes."""

        class TestClass:
            pass

        setattr(TestClass, CF_SERVICE_MARKER, True)
        assert is_cf_service(TestClass) is True

    def test_is_cf_service_negative(self) -> None:
        """Test is_cf_service returns False for unmarked classes."""

        class TestClass:
            pass

        assert is_cf_service(TestClass) is False

    def test_is_cf_module_positive(self) -> None:
        """Test is_cf_module returns True for marked classes."""

        class TestClass:
            pass

        setattr(TestClass, CF_SERVICE_META, ModuleMeta(name="test"))
        assert is_cf_module(TestClass) is True

    def test_is_cf_module_negative(self) -> None:
        """Test is_cf_module returns False for unmarked classes."""

        class TestClass:
            pass

        assert is_cf_module(TestClass) is False


@pytest.mark.unit
class TestMetaGetters:
    """Tests for metadata getter functions."""

    def test_get_service_meta_with_meta(self) -> None:
        """Test get_service_meta returns correct meta when present."""

        class TestClass:
            pass

        meta = ServiceMeta(name="test")
        setattr(TestClass, CF_SERVICE_META, meta)
        result = get_service_meta(TestClass)
        assert result is meta
        assert result.name == "test"

    def test_get_service_meta_without_meta(self) -> None:
        """Test get_service_meta returns None when no meta."""

        class TestClass:
            pass

        result = get_service_meta(TestClass)
        assert result is None

    def test_get_module_meta_with_meta(self) -> None:
        """Test get_module_meta returns correct meta when present."""

        class TestClass:
            pass

        meta = ModuleMeta(name="test")
        setattr(TestClass, CF_SERVICE_META, meta)
        result = get_module_meta(TestClass)
        assert result is meta
        assert result.name == "test"

    def test_get_module_meta_without_meta(self) -> None:
        """Test get_module_meta returns None when no meta."""

        class TestClass:
            pass

        result = get_module_meta(TestClass)
        assert result is None
