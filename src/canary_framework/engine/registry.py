"""Write-once service registry with parent-scope lookup."""

from __future__ import annotations

from canary_framework.common import DependencyInjectionError, ServiceEntry, ServiceNotFoundError
from canary_framework.common.logging import get_logger

_log = get_logger("registry")


class Registry:
    """Store local services with optional parent-scope lookup."""

    def __init__(self, parent: Registry | None = None) -> None:
        self.parent: Registry | None = parent
        self._by_name: dict[str, ServiceEntry] = {}
        self._by_class: dict[type, ServiceEntry] = {}

    def register(self, cls: type, name: str) -> None:
        """Register one class under an explicit local name."""
        if cls in self._by_class:
            return
        if name in self._by_name:
            raise ValueError(f"Service/Module '{name}' is already registered.")

        entry = ServiceEntry(cls=cls, name=name)
        self._by_name[name] = entry
        self._by_class[cls] = entry
        _log.debug("Registered service/module: %s -> %s", cls.__name__, name)

    def get_by_name(self, name: str) -> ServiceEntry:
        """Return an entry by name, searching the parent scope."""
        try:
            return self._by_name[name]
        except KeyError:
            if self.parent is not None:
                return self.parent.get_by_name(name)
            raise ServiceNotFoundError(f"Service with name '{name}' not found.") from None

    def get_by_class(self, cls: type) -> ServiceEntry:
        """Return an entry by class, searching the parent scope."""
        current: Registry | None = self
        while current is not None:
            if (entry := current._by_class.get(cls)) is not None:
                return entry
            current = current.parent
        raise ServiceNotFoundError(f"'{cls.__name__}' is not registered.") from None

    def get(self, cls: type) -> object:
        """Return an instantiated service by class."""
        entry = self.get_by_class(cls)
        if entry.instance is None:
            raise DependencyInjectionError(
                f"Service '{cls.__name__}' has no instance in the registry."
            )
        return entry.instance

    def has(self, cls: type) -> bool:
        """Report whether the class exists in this or a parent scope."""
        current: Registry | None = self
        while current is not None:
            if cls in current._by_class:
                return True
            current = current.parent
        return False

    def has_local(self, cls: type) -> bool:
        """Report whether the class exists in this scope."""
        return cls in self._by_class

    def local_entries(self) -> tuple[ServiceEntry, ...]:
        """Return local entries in registration order."""
        return tuple(self._by_class.values())

    def local_instances(self) -> tuple[object, ...]:
        """Return instantiated local services in registration order."""
        return tuple(e.instance for e in self._by_class.values() if e.instance is not None)


__all__ = ["Registry"]
