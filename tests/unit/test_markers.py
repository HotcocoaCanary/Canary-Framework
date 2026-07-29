"""Unit tests for common marker helpers."""

import pytest

from canary_framework.common import (
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ModuleMeta,
    RouterMeta,
    ServiceMeta,
    get_module_meta,
    get_router_meta,
    get_service_meta,
    is_cf_module,
    is_cf_router,
    is_cf_service,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "meta", [ServiceMeta(name="service"), RouterMeta(name="router"), ModuleMeta(name="module")]
)
def test_is_cf_service_recognizes_all_marked_node_kinds(meta: ServiceMeta) -> None:
    class TestClass:
        pass

    setattr(TestClass, CF_SERVICE_MARKER, True)
    setattr(TestClass, CF_SERVICE_META, meta)

    assert is_cf_service(TestClass) is True


@pytest.mark.unit
def test_is_cf_service_requires_service_marker() -> None:
    class TestClass:
        pass

    setattr(TestClass, CF_SERVICE_META, ServiceMeta(name="service"))

    assert is_cf_service(TestClass) is False


@pytest.mark.unit
@pytest.mark.parametrize(
    ("meta", "is_router", "is_module"),
    [
        (ServiceMeta(name="service"), False, False),
        (RouterMeta(name="router"), True, False),
        (ModuleMeta(name="module"), False, True),
    ],
)
def test_marker_helpers_match_exact_metadata_kind(
    meta: ServiceMeta, is_router: bool, is_module: bool
) -> None:
    class TestClass:
        pass

    setattr(TestClass, CF_SERVICE_META, meta)

    assert is_cf_router(TestClass) is is_router
    assert is_cf_module(TestClass) is is_module
    assert get_service_meta(TestClass) is meta
    assert get_router_meta(TestClass) is (meta if is_router else None)
    assert get_module_meta(TestClass) is (meta if is_module else None)


@pytest.mark.unit
def test_marker_helpers_return_none_without_metadata() -> None:
    class TestClass:
        pass

    assert get_service_meta(TestClass) is None
    assert get_router_meta(TestClass) is None
    assert get_module_meta(TestClass) is None
