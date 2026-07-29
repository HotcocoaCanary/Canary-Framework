"""Integration tests for dependency instantiation and wiring."""

import pytest

from canary_framework.common.config import CanaryConfig
from canary_framework.common.types import CF_SERVICE_MARKER, CF_SERVICE_META, ServiceMeta
from canary_framework.core.service import ServiceBase
from canary_framework.engine.container import DependencyEngine
from canary_framework.engine.registry import Registry


def _service(cls: type[ServiceBase]) -> type[ServiceBase]:
    setattr(cls, CF_SERVICE_MARKER, True)
    setattr(cls, CF_SERVICE_META, ServiceMeta(name=cls.__name__))
    return cls


@pytest.mark.integration
async def test_engine_instantiates_transitive_dependencies_once_and_wires_them() -> None:
    @_service
    class Deep(ServiceBase):
        pass

    @_service
    class Middle(ServiceBase):
        deep: Deep

    @_service
    class Consumer(ServiceBase):
        middle: Middle
        deep: Deep

    engine = DependencyEngine(children=(Consumer,), parent_registry=None, config=None)
    await engine.init()

    consumer = engine.registry.get(Consumer)
    middle = engine.registry.get(Middle)
    deep = engine.registry.get(Deep)
    assert consumer.middle is middle
    assert consumer.deep is deep
    assert middle.deep is deep
    assert tuple(type(item) for item in engine.registry.local_instances()) == (
        Consumer,
        Middle,
        Deep,
    )


@pytest.mark.integration
async def test_engine_reuses_parent_registry_dependency_and_propagates_config() -> None:
    @_service
    class Shared(ServiceBase):
        pass

    @_service
    class Consumer(ServiceBase):
        shared: Shared

    parent = Registry()
    parent.register(Shared, "Shared")
    shared = Shared()
    parent.get_by_class(Shared).instance = shared
    config = CanaryConfig(log_level="DEBUG")

    engine = DependencyEngine(children=(Consumer,), parent_registry=parent, config=config)
    await engine.init()

    consumer = engine.registry.get(Consumer)
    assert consumer.shared is shared
    assert consumer.config is config
    assert not engine.registry.has_local(Shared)
    assert shared not in engine.registry.local_instances()


@pytest.mark.integration
async def test_direct_children_follow_declaration_order_not_startup_order() -> None:
    @_service
    class Dependency(ServiceBase):
        pass

    @_service
    class Consumer(ServiceBase):
        dependency: Dependency

    engine = DependencyEngine(children=(Consumer, Dependency), parent_registry=None, config=None)
    await engine.init()

    assert tuple(type(node) for node in engine.direct_children) == (Consumer, Dependency)
    assert tuple(type(node) for node in engine.registry.local_instances()) == (
        Consumer,
        Dependency,
    )
