"""Contract tests for the explicit service declaration decorator."""

import inspect

import pytest

from canary_framework.common import get_service_meta, is_cf_service
from canary_framework.core import ServiceBase
from canary_framework.decorators import service


@pytest.mark.unit
def test_service_marks_explicit_service_subclass() -> None:
    @service()
    class ItemService(ServiceBase):
        pass

    assert issubclass(ItemService, ServiceBase)
    assert is_cf_service(ItemService)
    meta = get_service_meta(ItemService)
    assert meta is not None
    assert meta.name == "ItemService"
    assert ItemService.__cf_name__ == "ItemService"  # type: ignore[attr-defined]


@pytest.mark.unit
def test_service_requires_service_base() -> None:
    with pytest.raises(TypeError, match="must inherit from ServiceBase"):

        @service()  # type: ignore[arg-type]
        class NotAService:
            pass


@pytest.mark.unit
def test_service_has_no_legacy_keywords() -> None:
    parameters = inspect.signature(service).parameters
    assert tuple(parameters) == ()
    assert "config" not in parameters
    with pytest.raises(TypeError):
        service(config=object)  # type: ignore[call-arg]
