from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cf.core.registry.registry import Registry

T = object


class RouterContext:
    def __init__(self, service: object, registry: "Registry") -> None:
        self.service = service
        self._registry = registry

    def resolve(self, svc_cls: type[T]) -> T:
        return self._registry.get_instance(svc_cls)  # type: ignore[no-any-return]
