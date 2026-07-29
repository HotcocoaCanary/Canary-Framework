"""Integration tests for nested dependency scopes."""

from collections.abc import Callable
from typing import cast

import pytest

from canary_framework.common.types import (
    CF_SERVICE_MARKER,
    CF_SERVICE_META,
    ModuleMeta,
    ServiceMeta,
    get_module_meta,
)
from canary_framework.core.service import ServiceBase
from canary_framework.engine.container import DependencyEngine
from canary_framework.engine.registry import Registry


def _service(cls: type[ServiceBase]) -> type[ServiceBase]:
    setattr(cls, CF_SERVICE_MARKER, True)
    setattr(cls, CF_SERVICE_META, ServiceMeta(name=cls.__name__))
    return cls


def _module(*children: type) -> Callable[[type[ServiceBase]], type[ServiceBase]]:
    def decorate(cls: type[ServiceBase]) -> type[ServiceBase]:
        setattr(cls, CF_SERVICE_MARKER, True)
        setattr(cls, CF_SERVICE_META, ModuleMeta(name=cls.__name__, children=children))
        return cls

    return decorate


class _EngineModule(ServiceBase):
    engine: DependencyEngine

    async def _init(self) -> None:
        meta = get_module_meta(type(self))
        assert meta is not None
        self.engine = DependencyEngine(
            children=meta.children,
            parent_registry=cast(Registry, self._cf_parent_registry),
            config=self._cf_config,
        )
        await self.engine.init()

    async def _startup(self) -> None:
        await self.engine.startup()

    async def _shutdown(self) -> None:
        await self.engine.shutdown()

    async def _rollback_phase(self, *, started: bool) -> None:
        if started:
            await self.engine.rollback_started()
        else:
            await self.engine.rollback_initialized()


@pytest.mark.integration
async def test_sibling_modules_get_local_instances_of_same_dependency() -> None:
    @_service
    class Shared(ServiceBase):
        pass

    @_service
    class LeftConsumer(ServiceBase):
        shared: Shared

    @_service
    class RightConsumer(ServiceBase):
        shared: Shared

    @_module(LeftConsumer)
    class Left(_EngineModule):
        pass

    @_module(RightConsumer)
    class Right(_EngineModule):
        pass

    engine = DependencyEngine(children=(Left, Right), parent_registry=None, config=None)
    await engine.init()

    left = cast(_EngineModule, engine.registry.get(Left))
    right = cast(_EngineModule, engine.registry.get(Right))
    left_shared = left.engine.registry.get(Shared)
    right_shared = right.engine.registry.get(Shared)
    assert left_shared is not right_shared
    assert left.engine.registry.has_local(Shared)
    assert right.engine.registry.has_local(Shared)
    assert not engine.registry.has_local(Shared)


@pytest.mark.integration
async def test_parent_promoted_service_is_reused_by_sibling_modules() -> None:
    @_service
    class Shared(ServiceBase):
        pass

    @_service
    class LeftConsumer(ServiceBase):
        shared: Shared

    @_service
    class RightConsumer(ServiceBase):
        shared: Shared

    @_module(LeftConsumer)
    class Left(_EngineModule):
        pass

    @_module(RightConsumer)
    class Right(_EngineModule):
        pass

    engine = DependencyEngine(children=(Left, Shared, Right), parent_registry=None, config=None)
    await engine.init()

    shared = engine.registry.get(Shared)
    left = cast(_EngineModule, engine.registry.get(Left))
    right = cast(_EngineModule, engine.registry.get(Right))
    assert left.engine.registry.get(Shared) is shared
    assert right.engine.registry.get(Shared) is shared
    assert not left.engine.registry.has_local(Shared)
    assert not right.engine.registry.has_local(Shared)


@pytest.mark.integration
async def test_promoted_service_starts_before_nested_module_declared_first() -> None:
    events: list[str] = []

    @_service
    class Shared(ServiceBase):
        async def _init(self) -> None:
            events.append("shared-init")

        async def _startup(self) -> None:
            events.append("shared-startup")

    @_service
    class Middle(ServiceBase):
        shared: Shared

    @_service
    class Consumer(ServiceBase):
        middle: Middle

        async def _init(self) -> None:
            events.append("consumer-init")

        async def _startup(self) -> None:
            events.append("consumer-startup")

    @_module(Consumer)
    class Nested(_EngineModule):
        pass

    engine = DependencyEngine(children=(Nested, Shared), parent_registry=None, config=None)
    await engine.init()
    await engine.startup()

    assert events == [
        "shared-init",
        "consumer-init",
        "shared-startup",
        "consumer-startup",
    ]
