"""Unit tests for engine.utils module."""

import pytest

from canary_framework.common.markers import CF_NAME_ATTR, CF_SERVICE_MARKER, CF_SERVICE_META
from canary_framework.common.types import ServiceMeta
from canary_framework.engine.utils import make_subclass


@pytest.mark.unit
class TestMakeSubclass:
    """Tests for make_subclass function."""

    def test_basic_subclass_creation(self) -> None:
        """Test basic subclass creation."""

        class Original:
            pass

        class Base:
            pass

        meta = ServiceMeta(name="test", deps=[])

        new_cls = make_subclass(Original, Base, meta, "test_name")

        assert issubclass(new_cls, Base)
        assert issubclass(new_cls, Original)
        assert getattr(new_cls, CF_SERVICE_MARKER) is True
        assert getattr(new_cls, CF_SERVICE_META) is meta
        assert getattr(new_cls, CF_NAME_ATTR) == "test_name"

    def test_with_extra_marker(self) -> None:
        """Test subclass with extra marker."""

        class Original:
            pass

        class Base:
            pass

        meta = ServiceMeta(name="test", deps=[])
        extra_marker = "__extra_marker__"

        new_cls = make_subclass(Original, Base, meta, "test_name", extra_marker=extra_marker)

        assert getattr(new_cls, extra_marker) is True

    def test_preserves_module(self) -> None:
        """Test subclass preserves original module."""

        class Original:
            pass

        class Base:
            pass

        meta = ServiceMeta(name="test", deps=[])

        new_cls = make_subclass(Original, Base, meta, "test_name")

        assert new_cls.__module__ == Original.__module__

    def test_preserves_qualname(self) -> None:
        """Test subclass preserves original qualname."""

        class Original:
            pass

        class Base:
            pass

        meta = ServiceMeta(name="test", deps=[])

        new_cls = make_subclass(Original, Base, meta, "test_name")

        assert new_cls.__qualname__ == Original.__qualname__

    def test_with_deps_creates_placeholder_attrs(self) -> None:
        """Test that make_subclass creates class-level placeholder attributes for deps."""

        class Original:
            pass

        class Base:
            pass

        class DepA:
            pass

        class DepB:
            pass

        meta = ServiceMeta(name="test", deps=[DepA, DepB])

        new_cls = make_subclass(Original, Base, meta, "test_name")

        # Check that placeholder attributes exist as class attributes
        assert hasattr(new_cls, "dep_a")
        assert hasattr(new_cls, "dep_b")
        # Check __annotations__ includes the deps
        assert new_cls.__annotations__.get("dep_a") is DepA
        assert new_cls.__annotations__.get("dep_b") is DepB

    def test_with_deps_user_declared_not_overridden(self) -> None:
        """Test that user-declared annotations are not overridden."""

        class Original:
            custom_attr: str = ""

        class Base:
            pass

        class DepA:
            pass

        meta = ServiceMeta(name="test", deps=[DepA])

        new_cls = make_subclass(Original, Base, meta, "test_name")

        # User's declared annotation should be preserved
        assert new_cls.__annotations__.get("custom_attr") is str
        # Dep should still be added
        assert new_cls.__annotations__.get("dep_a") is DepA
        # Placeholder should exist
        assert hasattr(new_cls, "dep_a")
