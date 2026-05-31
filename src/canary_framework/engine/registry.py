"""Container — central registry of all registered services and modules.

Registry writes happen only during ``configure`` (single-threaded),
after which it is read-only.  No thread-safety needed for the
"write-once, read-many" pattern.
"""

from __future__ import annotations

from collections.abc import Iterator

from canary_framework.common import (
    CF_NAME_ATTR,
    ServiceEntry,
    ServiceMeta,
    ServiceNotFoundError,
    get_module_meta,
    get_service_meta,
)


class Registry:
    """Central registry — O(1) lookup by name or class, with parent chaining."""

    def __init__(self, parent: Registry | None = None) -> None:
        self.parent: Registry | None = parent
        self._by_name: dict[str, ServiceEntry] = {}
        self._by_class: dict[type, ServiceEntry] = {}

    def register(self, cls: type, *, meta: ServiceMeta | None = None) -> None:
        """Register a ``@service`` or ``@module`` class (idempotent)."""
        if cls in self._by_class:
            return

        if meta is None:
            mod_meta = get_module_meta(cls)
            meta = mod_meta if mod_meta.name else get_service_meta(cls)

        name: str = meta.name
        if name in self._by_name:
            raise ValueError(
                f"Service/Module '{name}' is already registered."
            )

        entry = ServiceEntry(
            cls=cls,
            name=name,
            deps=list(meta.deps),
            dep_names=[getattr(d, CF_NAME_ATTR, d.__name__) for d in meta.deps],
        )
        self._by_name[name] = entry
        self._by_class[cls] = entry

    def get_by_name(self, name: str) -> ServiceEntry:
        try:
            return self._by_name[name]
        except KeyError:
            raise ServiceNotFoundError(
                f"'{name}' is not registered. "
                f"Registered: {sorted(self._by_name)}"
            ) from None

    def get_by_class(self, cls: type) -> ServiceEntry:
        current: Registry | None = self
        while current is not None:
            try:
                return current._by_class[cls]
            except KeyError:
                current = current.parent
        raise ServiceNotFoundError(
            f"'{cls.__name__}' is not registered."
        ) from None

    def get_instance(self, cls: type) -> object:
        return self.get_by_class(cls).instance

    def has(self, cls: type) -> bool:
        current: Registry | None = self
        while current is not None:
            if cls in current._by_class:
                return True
            current = current.parent
        return False

    def all_entries(self) -> list[ServiceEntry]:
        return list(self._by_name.values())

    def names(self) -> list[str]:
        return list(self._by_name.keys())

    def __len__(self) -> int:
        return len(self._by_name)

    def __contains__(self, cls: type) -> bool:
        return self.has(cls)

    def __iter__(self) -> Iterator[ServiceEntry]:
        return iter(self._by_name.values())


__all__ = ["Registry"]
