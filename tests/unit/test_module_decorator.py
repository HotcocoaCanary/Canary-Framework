"""Contract tests for explicit module declarations."""

import inspect
from dataclasses import FrozenInstanceError

import pytest

from canary_framework.common import (
    CanaryConfig,
    get_module_meta,
    is_cf_module,
    is_cf_service,
)
from canary_framework.core import ModuleBase, RouterBase, ServiceBase
from canary_framework.decorators import get, module, router, service


@service()
class ItemService(ServiceBase):
    pass


@router(prefix="/items")
class ItemRouter(RouterBase):
    @get("")
    async def list_items(self) -> list[object]:
        return []


@pytest.mark.unit
def test_module_marks_explicit_module_subclass() -> None:
    @module(children=(ItemService, ItemRouter))
    class ItemModule(ModuleBase):
        pass

    assert issubclass(ItemModule, ModuleBase)
    assert issubclass(ItemModule, ServiceBase)
    assert is_cf_service(ItemModule)
    assert is_cf_module(ItemModule)


@pytest.mark.unit
def test_module_metadata_is_immutable_and_normalized() -> None:
    declared_children = [ItemService, ItemRouter]
    declared_tags = ["Items"]
    declared_security = ["bearerAuth"]

    @module(
        children=declared_children,
        prefix="/api",
        tags=declared_tags,
        security=declared_security,
    )
    class ItemModule(ModuleBase):
        pass

    declared_children.clear()
    declared_tags.clear()
    declared_security.clear()
    meta = get_module_meta(ItemModule)
    assert meta is not None
    assert meta.name == "ItemModule"
    assert meta.children == (ItemService, ItemRouter)
    assert meta.prefix == "/api"
    assert meta.tags == ("Items",)
    assert meta.security == ("bearerAuth",)
    with pytest.raises(FrozenInstanceError):
        meta.prefix = "/other"  # type: ignore[misc]


@pytest.mark.unit
def test_module_requires_module_base() -> None:
    with pytest.raises(TypeError, match="must inherit from ModuleBase"):

        @module()  # type: ignore[arg-type]
        class NotAModule(ServiceBase):
            pass


@pytest.mark.unit
def test_module_rejects_undecorated_children() -> None:
    class UndecoratedService(ServiceBase):
        pass

    with pytest.raises(TypeError, match="must be decorated by Canary Framework"):
        module(children=(UndecoratedService,))


@pytest.mark.unit
def test_module_rejects_config_class_as_child() -> None:
    class ModuleSettings(CanaryConfig):
        pass

    with pytest.raises(TypeError, match="cannot be a Module child"):
        module(children=(ModuleSettings,))


@pytest.mark.unit
def test_module_config_must_inherit_canary_config() -> None:
    with pytest.raises(TypeError, match="module config must inherit from CanaryConfig"):
        module(config=object)  # type: ignore[arg-type]

    class ModuleSettings(CanaryConfig):
        pass

    @module(config=ModuleSettings)
    class ConfiguredModule(ModuleBase):
        pass

    meta = get_module_meta(ConfiguredModule)
    assert meta is not None
    assert meta.config_cls is ModuleSettings


@pytest.mark.unit
def test_module_rejects_business_route_declarations() -> None:
    with pytest.raises(TypeError, match="may not declare business routes"):

        @module()
        class RoutedModule(ModuleBase):
            @get("/health")
            async def health(self) -> dict[str, bool]:
                return {"ok": True}


@pytest.mark.unit
def test_public_module_signature_replaces_legacy_services_keyword() -> None:
    parameters = inspect.signature(module).parameters
    assert "services" not in parameters
    assert "children" in parameters
    with pytest.raises(TypeError):
        module(services=())  # type: ignore[call-arg]
