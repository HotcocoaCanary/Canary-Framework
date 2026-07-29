"""服务注册表实现。

提供服务注册、查找和迭代功能，支持父子注册表继承。

Registry writes happen only during ``configure`` (single-threaded),
after which it is read-only. No thread-safety needed for the
"write-once, read-many" pattern.

Service registry implementation.

Provides service registration, lookup, and iteration with parent-child inheritance.
"""

from __future__ import annotations

from canary_framework.common import (
    DependencyInjectionError,
    ServiceEntry,
    ServiceMeta,
    ServiceNotFoundError,
)
from canary_framework.common.logging import get_logger

_log = get_logger("registry")


class Registry:
    """服务注册表，支持父子继承。

    注册表存储服务条目，支持通过名称或类查找。
    如果在当前注册表中找不到服务，会递归查找父注册表。

    Central registry — O(1) lookup by name or class, with parent chaining.
    """

    def __init__(self, parent: Registry | None = None) -> None:
        """初始化注册表。

        Args:
            parent: 父注册表，用于继承查找。

        Initialize the registry.

        Args:
            parent: Parent registry for inheritance lookups.
        """
        self.parent: Registry | None = parent
        self._by_name: dict[str, ServiceEntry] = {}
        self._by_class: dict[type, ServiceEntry] = {}

    def register(
        self,
        cls: type,
        name: str | None = None,
        *,
        meta: ServiceMeta | None = None,
    ) -> None:
        """Register a class by name or metadata, preserving insertion order.

        ``name`` is the compact local-registry API; ``meta`` remains accepted
        for transitional callers using the older metadata-based API.
        """
        if cls in self._by_class:
            return
        if name is None:
            if meta is None:
                raise TypeError("register() requires name or meta")
            name = meta.name
        elif meta is not None and meta.name != name:
            raise ValueError("name and meta.name must match")
        if name in self._by_name:
            raise ValueError(f"Service/Module '{name}' is already registered.")

        entry = ServiceEntry(cls=cls, name=name)
        self._by_name[name] = entry
        self._by_class[cls] = entry
        _log.debug("Registered service/module: %s -> %s", cls.__name__, name)

    def get_by_name(self, name: str) -> ServiceEntry:
        """按名称查找服务。

        Args:
            name: 服务名称。

        Returns:
            服务条目。

        Raises:
            ServiceNotFoundError: 如果服务未找到。

        Look up a service by name.

        Args:
            name: The service name.

        Returns:
            Service entry.

        Raises:
            ServiceNotFoundError: If the service is not found.
        """
        try:
            return self._by_name[name]
        except KeyError:
            if self.parent is not None:
                return self.parent.get_by_name(name)
            raise ServiceNotFoundError(
                f"Service with name '{name}' not found in registry."
            ) from None

    def get_by_class(self, cls: type) -> ServiceEntry:
        """按类查找服务。

        如果在当前注册表中找不到，会查找父注册表。

        Args:
            cls: 服务类。

        Returns:
            服务条目。

        Raises:
            ServiceNotFoundError: 如果服务未找到。

        Look up a service by class.

        Searches the parent registry if not found in the current registry.

        Args:
            cls: The service class.

        Returns:
            Service entry.

        Raises:
            ServiceNotFoundError: If the service is not found.
        """
        current: Registry | None = self
        while current is not None:
            try:
                return current._by_class[cls]
            except KeyError:
                current = current.parent
        raise ServiceNotFoundError(f"'{cls.__name__}' is not registered.") from None

    def get(self, cls: type) -> object:
        """Return an instantiated service from this or an ancestor scope."""
        entry = self.get_by_class(cls)
        if entry.instance is None:
            raise DependencyInjectionError(
                f"Service '{cls.__name__}' has no instance in the registry."
            )
        return entry.instance

    def has(self, cls: type) -> bool:
        """检查服务是否已注册。

        Args:
            cls: 服务类。

        Returns:
            如果服务已注册则返回True，否则返回False。

        Check if a service is registered.

        Args:
            cls: The service class.

        Returns:
            True if the service is registered, False otherwise.
        """
        current: Registry | None = self
        while current is not None:
            if cls in current._by_class:
                return True
            current = current.parent
        return False

    def has_local(self, cls: type) -> bool:
        """Return whether a class is registered in this scope itself."""
        return cls in self._by_class

    def local_entries(self) -> tuple[ServiceEntry, ...]:
        """Return this scope's entries in registration order."""
        return tuple(self._by_class.values())

    def local_instances(self) -> tuple[object, ...]:
        """Return instantiated objects owned by this scope."""
        return tuple(
            entry.instance for entry in self._by_class.values() if entry.instance is not None
        )

    def all_entries(self) -> list[ServiceEntry]:
        """获取所有服务条目。

        Returns:
            当前注册表中的所有服务条目列表。

        Get all service entries.

        Returns:
            List of all service entries in the current registry.
        """
        return list(self._by_name.values())

    def names(self) -> list[str]:
        """获取所有服务名称。

        Returns:
            当前注册表中的所有服务名称列表。

        Get all service names.

        Returns:
            List of all service names in the current registry.
        """
        return list(self._by_name.keys())


__all__ = ["Registry"]
